from enum import StrEnum
class Role(StrEnum):
    ADMIN='admin'
    ANALYST='analyst'
    VIEWER='viewer'
class RunStatus(StrEnum):
    QUEUED='queued'
    RUNNING='running'
    COMPLETED='completed'
    FAILED='failed'
class CaseStatus(StrEnum):
    DRAFT='draft'
    APPROVED='approved'
INPUTS=('staff_hours','energy_cost')
OUTPUTS=('visits','programs')
