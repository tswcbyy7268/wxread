# Ubuntu服务器运行

使用Python虚拟环境和systemd，无需Docker。每日任务为北京时间03:23、360次请求（约3小时），固定《三体》。

将仓库代码与 `install-server.sh` 放入一个私有安装目录。在该目录另建 `credentials.json`，字段为 `WXREAD_CURL_BASH`、`PUSH_METHOD`（pushplus）、`PUSHPLUS_TOKEN`、`WEREAD_API_KEY`；值均为字符串。该文件包含凭据，不能提交仓库。

以root执行 `bash install-server.sh`。安装器会建立独立wxread用户、虚拟环境和服务，测试代码并校验定时配置；安装后定时器保持关闭。

先执行 `systemctl start --no-block wxread-test.service` 做约5分钟验证。通过 `journalctl -u wxread-test.service --no-pager` 查看结果；应确认10次请求、官方实际统计增加，微信推送可用。测试期间暂停其他设备的阅读或听书。

验证成功后，停用GitHub的每日schedule，执行 `systemctl enable --now wxread.timer` 开启服务器每日任务，再用 `systemctl list-timers wxread.timer --all` 核对下一次时间。

项目目录 `/opt/wxread`，凭据 `/etc/wxread/credentials.json`，进度、官方统计和日志 `/var/lib/wxread`。安装目录中的凭据副本可删除。升级时保留凭据和进度目录。

手动继续当天正式任务：`systemctl start --no-block wxread.service`。停止当前任务：`systemctl stop wxread.service`。停止定时运行：`systemctl disable --now wxread.timer`。

短时网络故障沿用原监督进程，最多三次重启；登录失效、其他不可恢复错误、重试耗尽时停止。当天进度持久保存，再次启动继续剩余请求；完成当天目标后跳过。服务器停机错过的计划在定时器恢复后补触发。

开始与结束查询官方累计统计，并通过PushPlus汇报实际增量。统计包含账户同期阅读与听书，不保证挑战赛计入；PushPlus接受请求不等于微信送达。

部署后无需个人电脑开机。任务期间服务器需保持运行和联网，时间同步需正常；定时器没有随机延迟，但不承诺绝对实时。
