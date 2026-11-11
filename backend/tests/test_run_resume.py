import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.config.database import Base
from src.constants.enums import RunStatus
from src.models import BenchmarkSet, EfficiencyRun, PeriodObservation, Venue
from src.services import sensitivity
from src.services.run_service import _claim_run, _owned_write, execute_run


class ResumableRunTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            'sqlite://',
            connect_args={'check_same_thread': False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.db = self.Session()
        self.benchmark = BenchmarkSet(code='QY-TEST', name='闭环测试参照', period='2026Q3', source_file='test.csv')
        self.db.add(self.benchmark)
        self.db.flush()
        # Closed-form three-DMU sample from the README: [x,y]=[1,1],[2,1],[1,2].
        for code, x, y in (('QY-01', 1., 1.), ('QY-02', 2., 1.), ('QY-03', 1., 2.)):
            venue = Venue(code=code, name=code, district='测试片区', kind='综合文化场馆')
            self.db.add(venue)
            self.db.flush()
            self.db.add(
                PeriodObservation(
                    benchmark_id=self.benchmark.id,
                    venue_id=venue.id,
                    staff_hours=x,
                    energy_cost=1.,
                    visits=y,
                    programs=1.,
                )
            )
        self.db.commit()
        self.inputs = ['staff_hours']
        self.outputs = ['visits']

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _run(self, name):
        run = EfficiencyRun(
            name=name,
            benchmark_id=self.benchmark.id,
            inputs=self.inputs,
            outputs=self.outputs,
            sensitivity_count=1,
            status=RunStatus.QUEUED,
        )
        self.db.add(run)
        self.db.commit()
        return run

    def _expire_lease(self, run_id):
        self.db.execute(
            update(EfficiencyRun)
            .where(EfficiencyRun.id == run_id)
            .values(lease_expires_at=datetime.utcnow() - timedelta(seconds=1))
        )
        self.db.commit()

    def _interrupt_after(self, run_id, successful_solves, token='executor-old'):
        real_solve = sensitivity.solve_dmu
        calls = {'n': 0}

        def crashing_solve(*args, **kwargs):
            calls['n'] += 1
            if calls['n'] == successful_solves + 1:
                # Simulate the worker process disappearing mid-run. A
                # BaseException is not caught by execute_run, so the claim
                # remains RUNNING for a later executor to take over.
                raise KeyboardInterrupt('simulated worker interruption')
            return real_solve(*args, **kwargs)

        with patch('src.services.sensitivity.solve_dmu', side_effect=crashing_solve):
            with self.assertRaises(KeyboardInterrupt):
                execute_run(self.db, run_id, executor_token=token)
        self.db.rollback()
        return run_id

    def test_resume_reuses_benchmark_removal_progress(self):
        interrupted = self._run('移除情景中断续跑')
        # 3 baseline venues + 2 of the 3 removal-scenario targets.
        self._interrupt_after(interrupted.id, successful_solves=5)
        run = self.db.get(EfficiencyRun, interrupted.id)
        self.assertEqual(run.checkpoint['progress']['baseline_completed'], 3)
        removed = run.checkpoint['scenario_order'][0]
        scores = run.checkpoint['scenarios'][str(removed)]['scores']
        self.assertEqual(set(scores), {'1', '2'})

        self._expire_lease(interrupted.id)
        resumed_calls = {'n': 0}
        real_solve = sensitivity.solve_dmu

        def counting_solve(*args, **kwargs):
            resumed_calls['n'] += 1
            return real_solve(*args, **kwargs)

        with patch('src.services.sensitivity.solve_dmu', side_effect=counting_solve):
            self.assertTrue(execute_run(self.db, interrupted.id, executor_token='executor-new'))
        self.assertEqual(resumed_calls['n'], 1)

        control = self._run('移除情景一次跑完')
        self.assertTrue(execute_run(self.db, control.id, executor_token='executor-control'))
        self.assertEqual(self.db.get(EfficiencyRun, interrupted.id).result, self.db.get(EfficiencyRun, control.id).result)

    def test_exception_interruption_resumes_from_checkpoint(self):
        run = self._run('异常中断续跑')
        real_solve = sensitivity.solve_dmu
        calls = {'n': 0}

        def failing_solve(*args, **kwargs):
            calls['n'] += 1
            if calls['n'] == 3:
                raise RuntimeError('transient solver interruption')
            return real_solve(*args, **kwargs)

        with patch('src.services.sensitivity.solve_dmu', side_effect=failing_solve):
            self.assertFalse(execute_run(self.db, run.id, executor_token='executor-first'))
        run = self.db.get(EfficiencyRun, run.id)
        self.assertEqual(run.status, RunStatus.FAILED)
        self.assertEqual(set(run.checkpoint['baseline']), {'1', '2'})

        self.assertTrue(execute_run(self.db, run.id, executor_token='executor-retry'))
        run = self.db.get(EfficiencyRun, run.id)
        self.assertEqual(run.status, RunStatus.COMPLETED)
        self.assertEqual(run.checkpoint['progress']['baseline_completed'], 3)
        self.assertEqual(self.db.get(EfficiencyRun, run.id).claim_generation, 2)

    def test_duplicate_delivery_does_not_resolve_completed_run(self):
        run = self._run('重复投递')
        self.assertTrue(execute_run(self.db, run.id, executor_token='executor-first'))
        solved = {'n': 0}
        real_solve = sensitivity.solve_dmu

        def counting_solve(*args, **kwargs):
            solved['n'] += 1
            return real_solve(*args, **kwargs)

        with patch('src.services.sensitivity.solve_dmu', side_effect=counting_solve):
            self.assertFalse(execute_run(self.db, run.id, executor_token='executor-duplicate'))
        self.assertEqual(solved['n'], 0)
        self.assertEqual(self.db.get(EfficiencyRun, run.id).status, RunStatus.COMPLETED)

    def test_active_lease_blocks_second_executor_until_expiry(self):
        run = self._run('租约领取')
        self.assertTrue(_claim_run(self.db, run.id, 'executor-a'))
        # A second worker cannot take an actively leased run.
        self.assertFalse(_claim_run(self.db, run.id, 'executor-b'))
        self._expire_lease(run.id)
        # Once the lease expires, takeover is allowed and generation advances.
        self.assertTrue(_claim_run(self.db, run.id, 'executor-b'))
        self.assertEqual(self.db.get(EfficiencyRun, run.id).claim_generation, 2)
        self.assertEqual(self.db.get(EfficiencyRun, run.id).owner_token, 'executor-b')

    def test_resume_reuses_per_venue_checkpoint_and_matches_one_shot(self):
        interrupted = self._run('中断后复算')
        self._interrupt_after(interrupted.id, successful_solves=2)
        run = self.db.get(EfficiencyRun, interrupted.id)
        self.assertEqual(run.status, RunStatus.RUNNING)
        self.assertEqual(set(run.checkpoint['baseline']), {'1', '2'})
        self.assertEqual(run.checkpoint['progress']['baseline_completed'], 2)
        self.assertEqual(self.db.scalar(select(EfficiencyRun.claim_generation).where(EfficiencyRun.id == interrupted.id)), 1)

        self._expire_lease(interrupted.id)
        resumed_calls = {'n': 0}
        real_solve = sensitivity.solve_dmu

        def counting_solve(*args, **kwargs):
            resumed_calls['n'] += 1
            return real_solve(*args, **kwargs)

        with patch('src.services.sensitivity.solve_dmu', side_effect=counting_solve):
            self.assertTrue(execute_run(self.db, interrupted.id, executor_token='executor-new'))
        # One missing baseline venue plus the three removal-scenario targets.
        self.assertEqual(resumed_calls['n'], 4)

        control = self._run('一次跑完')
        self.assertTrue(execute_run(self.db, control.id, executor_token='executor-control'))
        self.db.refresh(self.db.get(EfficiencyRun, interrupted.id))
        resumed_result = self.db.get(EfficiencyRun, interrupted.id).result
        control_result = self.db.get(EfficiencyRun, control.id).result
        self.assertEqual(resumed_result, control_result)
        resumed_checkpoint = self.db.get(EfficiencyRun, interrupted.id).checkpoint
        self.assertEqual(resumed_checkpoint['progress']['phase'], 'completed')
        self.assertEqual(resumed_checkpoint['progress']['baseline_completed'], 3)
        self.assertEqual(self.db.get(EfficiencyRun, interrupted.id).claim_generation, 2)

    def test_old_executor_cannot_overwrite_taken_over_result(self):
        run = self._run('接管隔离')
        self._interrupt_after(run.id, successful_solves=2, token='executor-old')
        self._expire_lease(run.id)
        self.assertTrue(execute_run(self.db, run.id, executor_token='executor-new'))
        taken_over = self.db.get(EfficiencyRun, run.id)
        self.assertEqual(taken_over.status, RunStatus.COMPLETED)
        generation = taken_over.claim_generation
        good_result = dict(taken_over.result)

        # The old executor wakes up with its stale token/generation and tries
        # to persist progress and then a final result.
        stale_write = _owned_write(
            self.db,
            run.id,
            'executor-old',
            1,
            checkpoint={'baseline': {'1': {'theta': 999.}}, 'progress': {'phase': 'completed'}},
        )
        self.assertFalse(stale_write)
        stale_final = _owned_write(
            self.db,
            run.id,
            'executor-old',
            1,
            result={'fingerprint': 'stale', 'baseline': []},
            status=RunStatus.COMPLETED,
            lease_expires_at=None,
        )
        self.assertFalse(stale_final)
        self.assertFalse(execute_run(self.db, run.id, executor_token='executor-old'))

        taken_over = self.db.get(EfficiencyRun, run.id)
        self.assertEqual(taken_over.status, RunStatus.COMPLETED)
        self.assertEqual(taken_over.result, good_result)
        self.assertNotEqual(taken_over.result.get('fingerprint'), 'stale')
        self.assertEqual(taken_over.claim_generation, generation)

    def test_changed_sample_rejects_checkpoint_mixing(self):
        run = self._run('来源变化拒绝混用')
        self._interrupt_after(run.id, successful_solves=2)
        # A corrected/updated observation arrives after the checkpoint was
        # written. Reusing the two old baseline rows would mix samples.
        self.db.execute(
            update(PeriodObservation)
            .where(PeriodObservation.venue_id == 3)
            .values(staff_hours=9.)
        )
        self.db.commit()
        self._expire_lease(run.id)
        self.assertFalse(execute_run(self.db, run.id, executor_token='executor-new'))

        run = self.db.get(EfficiencyRun, run.id)
        self.assertEqual(run.status, RunStatus.FAILED)
        self.assertIn('拒绝混用', run.error)
        self.assertEqual(run.result, {})
        # The old partial checkpoint must not be combined with the new sample.
        self.assertEqual(run.checkpoint['progress']['baseline_completed'], 2)

    def test_changed_solving_spec_rejects_checkpoint_mixing(self):
        run = self._run('口径变化拒绝混用')
        self._interrupt_after(run.id, successful_solves=2)
        self.db.execute(
            update(EfficiencyRun)
            .where(EfficiencyRun.id == run.id)
            .values(sensitivity_count=3)
        )
        self.db.commit()
        self._expire_lease(run.id)
        self.assertFalse(execute_run(self.db, run.id, executor_token='executor-new'))
        run = self.db.get(EfficiencyRun, run.id)
        self.assertEqual(run.status, RunStatus.FAILED)
        self.assertIn('拒绝混用', run.error)


if __name__ == '__main__':
    unittest.main()
