# av-guard —— 需要凭证的 CLI 自动先开启 Agent Vault
#
# 包装 AV_GUARD_COMMANDS 里的命令：运行时若 AGENT_VAULT_ACTIVE 不是 true，
# 先执行 av-on（失败则中止），再用 command 调用真正的二进制。
# 已开启时只多一次字符串比较，几乎零开销。
#
# 用法：
#   - source 本插件前可自定义托管列表：AV_GUARD_COMMANDS=(gh glab)
#   - 运行时管理：av-guard add <cmd>... / av-guard rm <cmd>... / av-guard list
#
# 注意：若给托管命令定义了同名 alias，alias 会在函数之前展开，本插件不生效。

if (( ! ${+AV_GUARD_COMMANDS} )); then
    AV_GUARD_COMMANDS=(gh pi)
fi
# 注意：默认值判断要在 typeset 之前，typeset 会直接把变量创建出来
typeset -ga AV_GUARD_COMMANDS

# 真正干活的运行器，由各包装函数调用
_av_guard_run() {
    local cmd=$1
    shift

    # 二进制不存在时原样放行：保留原生 command not found 报错，
    # 也避免为打错的命令白白启动 vault
    if (( ! $+commands[$cmd] )); then
        command "$cmd" "$@"
        return
    fi

    if [[ ${AGENT_VAULT_ACTIVE:-} != true ]]; then
        if (( $+functions[av-on] )); then
            av-on || return
        else
            print -u2 "av-guard: av-on not found; running '$cmd' without Agent Vault"
        fi
    fi

    command "$cmd" "$@"
}

# 给指定命令安装包装函数
_av_guard_wrap() {
    local cmd
    for cmd in "$@"; do
        if (( $+aliases[$cmd] )); then
            print -u2 "av-guard: '$cmd' is an alias, unwrap the alias first"
            continue
        fi
        if (( $+functions[$cmd] )); then
            [[ $functions[$cmd] == *_av_guard_run* ]] && continue
            print -u2 "av-guard: '$cmd' already has a function, skip"
            continue
        fi
        functions[$cmd]="_av_guard_run ${(q)cmd} \"\$@\""
        (( ${AV_GUARD_COMMANDS[(Ie)$cmd]} )) || AV_GUARD_COMMANDS+=($cmd)
    done
}

# 运行时管理入口
av-guard() {
    case $1 in
        add)
            shift
            _av_guard_wrap "$@"
            ;;
        rm)
            shift
            local cmd
            for cmd in "$@"; do
                if (( $+functions[$cmd] )) && [[ $functions[$cmd] == *_av_guard_run* ]]; then
                    unfunction -- $cmd
                else
                    print -u2 "av-guard: '$cmd' is not wrapped by av-guard, skip"
                fi
                AV_GUARD_COMMANDS=(${AV_GUARD_COMMANDS:#$cmd})
            done
            ;;
        list)
            print -l -- $AV_GUARD_COMMANDS
            ;;
        *)
            print -u2 "usage: av-guard add|rm <cmd>... | av-guard list"
            return 2
            ;;
    esac
}

_av_guard_wrap $AV_GUARD_COMMANDS
