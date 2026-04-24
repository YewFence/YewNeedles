# AGENTS.md

这个仓库里的 task 以可移植性为先。新增任务如果需要兼容 macOS、Linux 和 Windows，优先使用 Python 实现；如果只依赖标准库，直接写纯 Python 脚本；如果需要第三方 Python 依赖，统一使用 uv 运行脚本和管理依赖。明显依赖类 Unix 语义的任务不用强行改写成 Python，可以继续使用 shell。
