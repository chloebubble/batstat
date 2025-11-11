function __gacp_usage
    printf "Usage: gacp [options]\n"
    printf "Options:\n"
    printf "  -m, --message <msg>   Use the provided commit message\n"
    printf "  -a, --auto            Force auto message generation (default)\n"
    printf "  -e, --edit            Edit the commit message in $EDITOR\n"
    printf "  -n, --dry-run         Print actions without running git\n"
    printf "  -b, --branch <name>   Target branch (default: current branch)\n"
    printf "  -r, --remote <name>   Remote to push to (default: origin)\n"
    printf "  -y, --yes             Skip confirmations; assume yes\n"
    printf "      --no-verify       Pass --no-verify to git commit/push\n"
    printf "  -v, --verbose         Echo commands as they run\n"
end

function __gacp_edit_message --argument-names initial_message
    set -l editor "$VISUAL"
    test -n "$editor"; or set editor "$EDITOR"
    test -n "$editor"; or set editor "nano"

    set -l tmp (mktemp /tmp/gacp-msg.XXXXXX)
    if test -n "$initial_message"
        printf "%s\n" "$initial_message" > "$tmp"
    end

    $editor "$tmp"
    set -l edited (string trim (cat "$tmp"))
    rm -f "$tmp"
    echo "$edited"
end

function __gacp_summary
    set -l diffstat (command git diff --cached --shortstat 2>/dev/null)
    if test -z "$diffstat"
        echo ""
        return 0
    end

    set -l files (string match -r --groups-only '([0-9]+) files?' $diffstat)
    test -n "$files"; or set files 0
    set -l insertions (string match -r --groups-only '([0-9]+) insertions?\(\+\)' $diffstat)
    test -n "$insertions"; or set insertions 0
    set -l deletions (string match -r --groups-only '([0-9]+) deletions?\(-\)' $diffstat)
    test -n "$deletions"; or set deletions 0

    echo "($files files, +$insertions -$deletions)"
end

function __gacp_autocommit_message
    set -l staged (command git diff --cached --name-only 2>/dev/null)
    set -l staged_count (count $staged)
    if test $staged_count -eq 0
        echo ""
        return 1
    end

    set -l only_docs 1
    set -l only_tests 1
    set -l only_lock 1
    set -l only_scripts 1
    set -l has_src 0
    set -l has_docs 0
    set -l has_tests 0
    set -l has_ignore 0
    set -l has_config 0
    set -l has_scripts 0

    for file in $staged
        if string match -r '^(README|docs/)' -- $file
            set has_docs 1
        else
            set only_docs 0
        end
        if string match -r '^(tests/|test_)' -- $file
            set has_tests 1
        else
            set only_tests 0
        end
        if test "$file" = "uv.lock"
            set has_config 1
        else
            set only_lock 0
        end
        if test "$file" = ".gitignore"
            set has_ignore 1
            set has_config 1
        end
        if test "$file" = "pyproject.toml"
            set has_config 1
        end
        if string match -r '^scripts/' -- $file
            set has_scripts 1
        else
            set only_scripts 0
        end
        if string match -r '^src/' -- $file
            set has_src 1
        end
    end

    set -l config_only $has_config
    if test $config_only -eq 1
        if test $has_src -eq 1 -o $has_docs -eq 1 -o $has_tests -eq 1 -o $has_scripts -eq 1
            set config_only 0
        end
    end

    set -l new_src_count 0
    for file in (command git diff --cached --name-only --diff-filter=A 2>/dev/null)
        if string match -r '^src/' -- $file
            set new_src_count (math $new_src_count + 1)
        end
    end

    set -l diff_py (command git diff --cached pyproject.toml 2>/dev/null)
    set -l new_version ""
    set -l old_version ""
    for line in $diff_py
        if test -z "$new_version"
            set -l candidate_new (string match -r --groups-only '^\+version = \"([^\"]+)\"' -- $line)
            if test -n "$candidate_new"
                set new_version $candidate_new
            end
        end
        if test -z "$old_version"
            set -l candidate_old (string match -r --groups-only '^\-version = \"([^\"]+)\"' -- $line)
            if test -n "$candidate_old"
                set old_version $candidate_old
            end
        end
    end

    set -l first $staged[1]
    test -n "$first"; or set first "files"
    set -l label (basename "$first")

    set -l summary (__gacp_summary)
    test -n "$summary"; and set summary " $summary"

    if test -n "$new_version"; and test -n "$old_version"
        echo "chore(release): v$new_version$summary"
        return 0
    end

    if test $only_lock -eq 1
        echo "chore(lock): update uv.lock$summary"
        return 0
    end

    if test $staged_count -eq 1 -a $has_ignore -eq 1
        echo "chore(git): update .gitignore$summary"
        return 0
    end

    if test $only_docs -eq 1
        echo "docs: refresh docs$summary"
        return 0
    end

    if test $only_tests -eq 1
        echo "test: update tests$summary"
        return 0
    end

    if test $only_scripts -eq 1
        echo "chore(scripts): update helpers$summary"
        return 0
    end

    if test $config_only -eq 1
        echo "chore(config): refresh project settings$summary"
        return 0
    end

    if test $new_src_count -gt 0
        echo "feat: update $label$summary"
        return 0
    end

    if test $has_src -eq 1
        echo "fix: update $label$summary"
        return 0
    end

    set -l focus_tokens
    if test $has_src -eq 1
        contains -- code $focus_tokens; or set focus_tokens $focus_tokens code
    end
    if test $has_docs -eq 1
        contains -- docs $focus_tokens; or set focus_tokens $focus_tokens docs
    end
    if test $has_tests -eq 1
        contains -- tests $focus_tokens; or set focus_tokens $focus_tokens tests
    end
    if test $has_scripts -eq 1
        contains -- scripts $focus_tokens; or set focus_tokens $focus_tokens scripts
    end
    if test $has_config -eq 1
        contains -- config $focus_tokens; or set focus_tokens $focus_tokens config
    end

    if test (count $focus_tokens) -eq 0
        set focus_tokens $label
    end

    set -l readable_tokens
    for token in $focus_tokens
        switch $token
            case code
                set readable_tokens $readable_tokens "code"
            case docs
                set readable_tokens $readable_tokens "docs"
            case tests
                set readable_tokens $readable_tokens "tests"
            case scripts
                set readable_tokens $readable_tokens "scripts"
            case config
                set readable_tokens $readable_tokens "config files"
            case '*'
                set readable_tokens $readable_tokens $token
        end
    end

    set -l focus_text ""
    switch (count $readable_tokens)
        case 1
            set focus_text $readable_tokens[1]
        case 2
            set focus_text "$readable_tokens[1] & $readable_tokens[2]"
        case '*'
            set focus_text "multiple areas"
    end

    set -l scope_tag ""
    if test (count $focus_tokens) -eq 1
        set scope_tag $focus_tokens[1]
        if not string match -r '^[a-z0-9_-]+$' -- $scope_tag
            set scope_tag ""
        end
    end

    set -l type "chore"
    if test $has_src -eq 1
        if test $new_src_count -gt 0
            set type "feat"
        else
            set type "fix"
        end
    else if test $has_tests -eq 1 -a $has_docs -eq 0 -a $has_scripts -eq 0
        set type "test"
    else if test $has_docs -eq 1 -a $has_scripts -eq 0
        set type "docs"
    else if test $has_scripts -eq 1 -a $has_src -eq 0 -a $has_docs -eq 0
        set type "chore"
    end

    set -l scope_part ""
    if test -n "$scope_tag"
        switch $type
            case docs test
                # omit scope details
            case '*'
                set scope_part "($scope_tag)"
        end
    end

    echo "$type$scope_part: update $focus_text$summary"
end

function __gacp_run
    set -l pretty (string join ' ' (string escape -- $argv))
    if test "$__GACP_DRY_RUN" = "1"
        echo "dry-run> $pretty"
        return 0
    end
    if test "$__GACP_VERBOSE" = "1"
        echo "+ $pretty"
    end
    command $argv
end

function gacp --description "git add/commit/push helper with optional auto messages"
    argparse --name=gacp \
        'm/message=' \
        'a/auto' \
        'e/edit' \
        'n/dry-run' \
        'b/branch=' \
        'r/remote=' \
        'y/yes' \
        'v/verbose' \
        'h/help' \
        'no-verify' \
        -- $argv
    or return $status

    if set -q _flag_help
        __gacp_usage
        return 0
    end

    set -l dry_run 0
    set -l verbose 0
    set -l yes_flag 0
    set -l auto_mode 0
    set -l edit_flag 0
    set -l no_verify 0

    set -q _flag_dry_run; and set dry_run 1
    set -q _flag_verbose; and set verbose 1
    set -q _flag_yes; and set yes_flag 1
    set -q _flag_auto; and set auto_mode 1
    set -q _flag_edit; and set edit_flag 1
    set -q _flag_no_verify; and set no_verify 1

    set -l message ""
    if set -q _flag_message[1]
        set message $_flag_message[1]
    else
        set auto_mode 1
    end

    set -l remote "$GACP_REMOTE"
    test -n "$remote"; or set remote "origin"
    if set -q _flag_remote[1]
        set remote $_flag_remote[1]
    end

    set -l branch ""
    if set -q _flag_branch[1]
        set branch $_flag_branch[1]
    else if test -n "$GACP_BRANCH"
        set branch "$GACP_BRANCH"
    end

    command git rev-parse --is-inside-work-tree >/dev/null 2>&1
    or begin
        echo "gacp: not inside a git repository" >&2
        return 1
    end

    if test -z "$branch"
        set branch (command git rev-parse --abbrev-ref HEAD 2>/dev/null)
        if test "$branch" = "HEAD"
            echo "gacp: detached HEAD; specify --branch" >&2
            return 1
        end
    end

    command git remote get-url "$remote" >/dev/null 2>&1
    or begin
        echo "gacp: remote '$remote' not found" >&2
        return 1
    end

    set -l status_lines (command git status --short)
    if test (count $status_lines) -eq 0
        echo "gacp: no changes to commit"
        return 0
    end

    set -g __GACP_DRY_RUN $dry_run
    set -g __GACP_VERBOSE $verbose

    __gacp_run git add .
    or begin
        set -e __GACP_DRY_RUN
        set -e __GACP_VERBOSE
        return $status
    end

    set -l staged_after (command git diff --cached --name-only)
    if test (count $staged_after) -eq 0
        echo "gacp: git add produced no staged changes"
        set -e __GACP_DRY_RUN
        set -e __GACP_VERBOSE
        return 1
    end

    if test $auto_mode -eq 1
        set message (__gacp_autocommit_message)
    end

    if test -z "$message"
        echo "gacp: unable to determine commit message" >&2
        set -e __GACP_DRY_RUN
        set -e __GACP_VERBOSE
        return 1
    end

    if test $edit_flag -eq 1
        set message (__gacp_edit_message "$message")
    end

    if test $yes_flag -ne 1
        echo "Proposed commit message:"
        echo "  $message"
        read -l choice -P "Use this message? [Y/n/edit] "
        switch (string lower -- "$choice")
            case '' 'y' 'yes'
                # keep
            case 'n' 'no'
                read -l message -P "Enter commit message: "
            case 'e' 'edit'
                set message (__gacp_edit_message "$message")
            case '*'
                set message "$choice"
        end
    end

    if test -z "$message"
        echo "gacp: commit message cannot be empty" >&2
        set -e __GACP_DRY_RUN
        set -e __GACP_VERBOSE
        return 1
    end

    set -l commit_cmd git commit
    if test $no_verify -eq 1
        set commit_cmd $commit_cmd --no-verify
    end
    set commit_cmd $commit_cmd -m "$message"
    __gacp_run $commit_cmd
    or begin
        set -e __GACP_DRY_RUN
        set -e __GACP_VERBOSE
        return $status
    end

    set -l needs_upstream 0
    set -l current_branch (command git rev-parse --abbrev-ref HEAD 2>/dev/null)
    if test "$branch" = "$current_branch"
        command git rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1
        or set needs_upstream 1
    else
        set needs_upstream 1
    end

    set -l push_cmd git push
    if test $needs_upstream -eq 1
        set push_cmd $push_cmd -u
    end
    if test $no_verify -eq 1
        set push_cmd $push_cmd --no-verify
    end
    set push_cmd $push_cmd $remote $branch

    __gacp_run $push_cmd
    set -l push_status $status

    set -e __GACP_DRY_RUN
    set -e __GACP_VERBOSE

    return $push_status
end
