该仓库放了 YewFence 的一些小工具

## mise task
这个仓库里的 mise task 如果需要兼容 macOS、Linux 和 Windows，优先使用 Python 实现；如果只依赖标准库，直接写纯 Python 脚本；如果需要第三方 Python 依赖，使用 uv shebang。如果是复杂任务考虑放到 `packages` 目录下写成正式的 Python 包。明显依赖类 Unix 语义的任务不用强行改写成 Python，可以继续使用 shell。
