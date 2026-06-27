
local -a precommands
precommands=(infisical fnox yews)

_exec_run_default_completion() {
    local completion_func
    completion_func="_$words[1]"

    if (( $+functions[$completion_func] )); then
        "$completion_func" "$@"
    else
        _default "$@"
    fi
}

_exec_run_wrapper() {
    local -i sep

    sep=${words[(i)--]}

    if [[ "$words[2]" == "run" ]] && (( sep > 2 && sep < CURRENT )); then
        words=( "${words[@]:$sep}" )
        (( CURRENT -= sep ))
        _normal
    else
        _exec_run_default_completion "$@"
    fi
}

for cmd in $precommands; do
    compdef _exec_run_wrapper $cmd
done
