# 栖原场馆效率评议席 · Venue Frontier

把同季度机构的多项投入、产出与同伴参照放在一起，为现场复核形成一份可追溯的改进假设。

栖原文化设施研究室的18位分析员原先按到访人次/工时等单一比率分别排序，规模差异与投入结构难以一起讨论，少数高表现参照对其他机构分数的影响也不透明。上游为机构级季度汇总，本项目替代多投入产出求解、参照解释、敏感性与评议归档，下游机构联络员组织现场复核。全部数据均为合成机构数据；不包含个人记录，不进行个人绩效或自动拨款。

## 启动与账号

```sh
cp .env.example .env
docker compose up -d --build
docker compose ps
docker compose exec -T backend python -m scripts.seed_demo
```

前端 http://localhost:18214，后端 http://localhost:19214，API文档 http://localhost:19214/docs。前端`/api/`由Nginx剥去前缀后代理，直接访问后端不带`/api`。结束：`docker compose down -v --remove-orphans`（删除本项目演示数据库和卷）。

共用密码`Qiyuan2026!`。

| 邮箱 | 角色 | 页面与动作 |
|---|---|---|
| admin@qiyuan.demo | admin / 评议负责人 | 六页；登记、导入、求解、提案、审阅批准、下载 |
| analyst@qiyuan.demo | analyst / 场馆分析员 | 六页；登记、导入、求解、提案、下载；不能批准 |
| viewer@qiyuan.demo | viewer / 机构联络员 | 六页只读，可下载获批机构评议CSV；不能写入或批准 |

JWT有效期8小时，密码带盐PBKDF2-SHA256；独立审计与错误中间件，登录每来源每分钟最多30次。对外部署前更换演示凭证与JWT密钥。

## 一天的工作剧本

1. 10:00 沈原登录，查看2026Q3的24个机构，原始文件为`qy-venues-2026.csv`。
2. 10:05 复核水岸青年馆QY-05的人员工时、能源费用、到访人次与项目场次。
3. 10:10 选择2026Q3参照集、两投入两产出、移除3个高权重共同标杆，提交求解。
4. 10:12 worker执行CCR基线与固定θ的松弛阶段；在结果页核对目标机构的参照λ。
5. 10:20 选择水岸青年馆，查看投入投影、额外松弛与产出盈余，辨别它们各自的口径。
6. 10:30 看三个共同标杆逐一移除情景；每情景对所有原目标使用同一R减b，读出参照依赖。
7. 11:00 写下“开放时段与照明排程复核”假设，先核对统计边界，安排两周现场观察。
8. 11:20 许栖使用admin审阅，何禾使用viewer下载包含研究指纹的机构评议CSV。

## CCR、松弛与敏感性的口径

输入为3–100个同一期机构观察，已登记场馆编号唯一；`staff_hours`与`energy_cost`必须为正，`visits`与`programs`非负。每个BenchmarkSet只描述一个统一季度，不跨期拼接。可选至少一项投入及一项产出。数据集导入后保持不变，更正请导入新版本。

第一阶段变量为参照强度λ与径向效率θ：

```
min θ
Σ_j λ_j X_ij ≤ θ X_i0     对每项投入i
Σ_j λ_j Y_rj ≥ Y_r0       对每项产出r
λ_j ≥ 0, θ ≥ 0
```

这是投入导向CCR/规模报酬不变模型，不添加`Σλ=1`。基线所有目标共用同一同期参照集，并包含自身，因此有效基线θ通常在0–1内。

第二阶段固定θ，再最大化各项标准化投入松弛和产出盈余之和：投入松弛`θX₀−ΣλX`，产出盈余`ΣλY−Y₀`。各列按完整基线参照集的列最大值缩放，情景继续使用同一缩放。输出原单位投入投影`ΣλX`、产出投影与松弛，径向缩减和额外松弛分别呈现。θ≈1且标准化松弛均在容差内才标为“本次强有效”。返回一组最优λ，λ可以不和为1，不能解释为概率；多重最优解可能产生其他同样有效的参照组合。

敏感性先对每个参照机构累计其在“其他目标”解中的λ，不计目标自身λ，按累计值降序选择最多3个高权重共同标杆，同分按机构代码排序。对每个标杆b单独重新求解：原目标集完全不变，所有目标统一使用`R\{b}`。被移除机构仍作为目标，其自身被排出参照，所以该目标θ可能超过1，这是超效率式的反事实分数，不把它裁剪成1。其余目标仍可使用自身。移除前后θ差异描述参照依赖，不代表机构真实表现或资源发生改变；若没有外部参照λ，敏感性列表为空，并不虚构标杆。

求解采用SciPy `linprog(method='highs')`；0最优、2不可行、3无界等状态分别保存，不给失败情景填假θ。正投入和θ非负的有效模型不可能向负无穷无界；仍显式处理求解器返回状态。固定θ的第二阶段失败也不会冒充完成。实际状态码口径参照[SciPy linprog官方文档](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linprog.html)。

## 失败态、边界与复算

- 零/负投入、负产出、非有限值、重复观察、空参照、样本不足、非法字段均拒绝。全零产出目标在数学上θ=0且明确标记，不解释为实际可将所有投入归零。
- 目标有某项正产出而移除后的参照集无法供给时，情景可为infeasible；基线自含一般保证可行。
- DEA分数对异常参照和变量选择敏感，不自动识别机构使命差异、服务质量或投入可控性。高相对效率不等于绝对最优；低分不直接构成削减资源的依据。
- 规范JSON SHA256包含全部稳定排序机构观察、机构标识、全部数值、参照集/季度、输入输出字段、敏感性数量、基线自含与统一移除规则、算法版本。没有随机计算；HiGHS返回一组最优解，不声称参照权重唯一。
- 测试含闭式三DMU：[x,y]=[1,1],[2,1],[1,2]，基线θ=[.5,.25,1]；统一移除C后θ=[1,.5,2]，以及单位缩放不变、第二阶段松弛、真实不可行与求解器状态验证。

## 页面、实体与共享组件

六页：研究总览、同期样本、效率求解、参照与敏感性、改进假设、评议留痕。五核心实体BenchmarkSet、Venue、PeriodObservation、EfficiencyRun、ImprovementCase各有model/schema/service/controller/route/前端API/store/页面链路。

共用业务组件BenchmarkSelect、EfficiencyPlot、FrontierSummary、RunTable；通用PageHeading/StatusBadge/ErrorNotice/EmptyState。useTask管理恢复状态，usePolling只刷新运行中研究，createStore使用React原生useSyncExternalStore。

共享枚举：后端`backend/src/constants/enums.py`的Role/RunStatus/CaseStatus与INPUTS/OUTPUTS；RunStatus用于run_service和worker，CaseStatus用于case_service，角色授权在utils/auth。前端`frontend/src/constants/enums.ts`的roles/statuses/inputKeys/outputKeys/fields用于App、StatusBadge、求解选择和结果展示。

## 技术、环境与目录

| 层 | 实现 |
|---|---|
| frontend | React18.3.1、TypeScript、Vite6.4.6内置esbuild automatic JSX、Nginx1.27 |
| backend | Python3.11、FastAPI、SQLAlchemy、psycopg3、PyJWT |
| 算法 | NumPy、SciPy1.17.1/HiGHS两阶段线性规划 |
| worker | 单Python消费者；DB任务状态为事实源，Redis唤醒并恢复queued/running |
| db/redis | PostgreSQL16、Redis7 AOF |

恰好五服务，均有healthcheck；backend等db/redis healthy；worker再等backend初始化；frontend等backend。命名卷包括数据库、Redis、后端/worker共享产物。当前求解结果在DB、CSV实时生成，共享卷保留扩展通道。初始schema由metadata创建，migrations记录v1自然键，未包含生产schema升级工具。

`frontend/src/{api,stores,types,components/common,hooks,pages,router,utils,constants}`；`backend/src/{routes,controllers,services,models,schemas,middlewares,utils,constants,config}`；`backend/scripts/seed_demo.py`。

| 环境变量 | 默认 |
|---|---|
| COMPOSE_PROJECT_NAME | venue-frontier，顶层name与容器命名适配中文父目录 |
| FRONTEND_PORT/BACKEND_PORT/DB_PORT | 18214/19214/17714 |
| DB_PASSWORD | 本地PostgreSQL演示密码 |
| JWT_SECRET | 项目独立签名密钥 |
| SEED_DEMO | true自动seed，失败记日志但允许API启动 |

seed自然键为账号邮箱、参照集code、场馆code、(benchmark_id,venue_id)、研究名称、假设标题；已存在记录不覆盖用户修改。初始24机构×两个季度=48观察，2研究、1个获批假设；数值生成固定seed91。其余测试数据由独立验收脚本创建。

本地开发：启动db/redis，在backend安装requirements、配置DATABASE_URL/REDIS_URL/JWT_SECRET，运行`uvicorn src.main:app --reload`及`python -m src.worker`；前端`npm ci && npm run dev`，默认/api代理到19214，如本地API用8000需同步修改代理。测试报告和截图在批次根`test-artifacts/gb-0010/`。MIT License，见LICENSE。
