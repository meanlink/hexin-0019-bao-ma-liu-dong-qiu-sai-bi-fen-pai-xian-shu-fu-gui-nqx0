# 报码 · 流动球赛比分牌线束复归

东湾社区联赛有四名赛事技术员和多块便携式两位比分牌。工作人员过去在纸上记“左排缺灯”“插头重拔”，既难区分接触漂移与线序错位，也会重复领用同一条备线。相同板子拔插或更换线束后，纸上已签好的旧检记录仍可能随车。

报码提供纯后端 JSON API。它以比分牌、校验通过的表计和灯段夹具为输入，记录两次扫描的点亮掩码、点亮稳定时间及电流。复归票串起故障建议、备件领用、装配版次和独立复测。赛事装车人员只取当前已核验的随车设备清单。

| 角色 | 演示账号及密码 | 典型动作 |
|---|---|---|
| operator | operator / operator-hexin-demo | 开诊断扫测、填写响应、领退备件、安装 |
| admin | admin / admin-hexin-demo | 可完成上述动作，独立复测后签发随车 |
| viewer | viewer / viewer-hexin-demo | 查看设备、夹具、扫测、故障建议、恢复票及随车清单 |

## 一个赛前技术班

1. 08:00，班组用已校验的 MTR-N7 测东湾比分牌 FOX-07，留档线束版次 1。
2. 08:08，按熄灭、左排、右排、边沿、交替、全亮六种图案扫两次。漏掉一个图案时不启动诊断。
3. 08:12，模型从信号中选择互信息特征，提出 mapping_shift 线序错位建议。写入修订扫测会使旧分类过期。
4. 08:20，装配员分配 HAR-2X7-A，另一块板无法重领，单排 HAR-1X7-C 无法为双排面板领用。
5. 08:28，记录安装说明并置为线束版次 2。装车人员此时仍看不到 FOX-07。
6. 08:40，另一位技术员用 MTR-R2 扫全量图案。发现全亮图案的重复位翻转后，签收被阻止，技术员查好接头并重测。
7. 08:50，复核员以更新后的复测快照签发，随车清单带上线束版次、复测表计和签发号。

## 启动

    cp .env.example .env
    docker compose up -d --build --wait
    curl http://127.0.0.1:18368/health
    curl http://127.0.0.1:18368/openapi.json
    docker compose exec -T backend python -m scripts.seed_demo

网关 18368，直连 FastAPI 19368，开发库 PostgreSQL 17868。API 和分类 worker 共用 Python 镜像，Redis 提供运行健康心跳。SEED_DEMO 控制初始化演示数据。登录 /auth/login 后用 Bearer token 调用领域接口。独立开发时先启动 Redis 与 PostgreSQL，再按 backend/requirements.txt 安装包，从 backend 目录使用 docker-compose.yml 中 API 和 worker 的环境变量与启动命令。

## 特征、模型和签发

- 每个图案使用 14 位灯段掩码。错误位分为预期未亮、意外点亮、重复扫描改变、两次都重复错位、左右排错误。计时以毫秒计，电流以 mA 计。
- 方差筛选剔除恒定特征，互信息最多选择 5 项，随后标准化并拟合三类逻辑回归。留出按参考扫描组划分。API 返回训练参考摘要、筛选结果、概率、混淆矩阵和平衡准确率。
- 线序错位需更换对应排数的线束。装配使旧扫测失效。复归签发逐图案比对两次实际掩码、稳定时间及电流容差，同时校验线束版次、复测版次，以及与诊断不同的表计和技术员。
- 演示参考包由带已知故障类型的合成板卡读数构造。真实赛事组须用现场参考件复核模型指标，签发依据保留独立实测。

| 目录 | 职责 |
|---|---|
| backend/domain | 设备、夹具、扫测、特征选择、备件及装车复归 |
| backend/migrations | 设备状态、扫测、诊断和实物签收约束 |
| backend/core | HTTP 服务、授权、审计与任务队列 |

设备阶段 check_due、repairing、awaiting_retest 和 ready 在 010_scoreboard_gear.sql、boards.py、sweep_rules.py、cards.py、road_release.py 使用。diagnosis 和 retest 在 020_pattern_sweeps.sql、signal_input.py、sweeps.py 和各业务校验中使用。reseat 与 swap 在 030_restore_cards.sql、card_input.py 和 cards.py 使用。

代码使用 MIT License。
