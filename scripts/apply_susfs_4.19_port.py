#!/usr/bin/env python3
"""
apply_susfs_4.19_port.py

Port the SukiSU-Ultra "GKI-flavored" SUSFS onto a non-GKI 4.19 kernel
(OnePlus 8T / kebab / sm8250, LineageOS 23.2 = 4.19.325).

SukiSU-Ultra's driver expects its own SUSFS interface (SUSFS_MAGIC, void* command
args, extra functions) that upstream only ships for GKI (5.10+). It turns out the
GKI SUSFS core (ShirkNeko/susfs4ksu @ gki-android12-5.10) is ~95% source-compatible
with 4.19; this script applies the handful of real 4.19 fixups, plus the two
non-GKI build fixes the SukiSU-Ultra driver itself needs.

Run order (see build-sukisu-kernel.sh):
  1. integrate SukiSU-Ultra (builtin) + apply_ksu_hooks.py
  2. copy GKI SUSFS sources (susfs.c/sus_su.c -> fs/, *.h -> include/linux/)
  3. patch -p1 < 50_add_susfs_in_gki-android12-5.10.patch   (forward, fuzz=3)
  4. THIS script
  5. configure (enable core SUSFS, disable OPEN_REDIRECT/SUS_MAP) + build

Idempotent and anchor-based: a no-op if already applied, hard error if an anchor
is missing (so upstream drift is caught instead of silently mis-patched).

Usage: python3 apply_susfs_4.19_port.py <kernel_root>
"""
import os
import re
import sys

K = sys.argv[1] if len(sys.argv) > 1 else "."
failed = []


def edit(path, old, new, marker, count=1):
    """Replace `old`->`new`. Skip if `marker` already present. Require `count` hits."""
    full = os.path.join(K, path)
    if not os.path.exists(full):
        print(f"[!] {path}: missing file"); failed.append(path); return
    s = open(full).read()
    if marker in s:
        print(f"[=] {path}: already ported"); return
    n = s.count(old)
    if n != count:
        print(f"[!] {path}: anchor count {n} != {count}"); failed.append(path); return
    open(full, "w").write(s.replace(old, new))
    print(f"[+] {path}: ported ({count})")


def edit_re(path, pattern, repl, marker, flags=re.S):
    full = os.path.join(K, path)
    if not os.path.exists(full):
        print(f"[!] {path}: missing file"); failed.append(path); return
    s = open(full).read()
    if marker in s:
        print(f"[=] {path}: already ported"); return
    s2, n = re.subn(pattern, repl, s, count=1, flags=flags)
    if n != 1:
        print(f"[!] {path}: regex matched {n}"); failed.append(path); return
    open(full, "w").write(s2)
    print(f"[+] {path}: ported (regex)")


# ============================================================================
# PART A — SukiSU-Ultra driver: two non-GKI (<5.10) build fixes
#          (apply to the integrated driver under KernelSU/kernel/)
# ============================================================================
KSU = "KernelSU/kernel"

# A1: selinux_hide is GKI-only; its header is included only for >=5.10 but ksud.c
#     calls the handlers unconditionally. Provide no-op stubs for <5.10.
edit(f"{KSU}/ksu.c",
     '#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 10, 0)\n'
     '#include "feature/selinux_hide.h"\n#endif\n',
     '#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 10, 0)\n'
     '#include "feature/selinux_hide.h"\n#else\n'
     'static inline void ksu_selinux_hide_init(void) {}\n'
     'static inline void ksu_selinux_hide_exit(void) {}\n'
     'static inline void ksu_selinux_hide_drop_backup_if_unused(void) {}\n'
     'static inline void ksu_selinux_hide_handle_second_stage(void) {}\n'
     'static inline void ksu_selinux_hide_handle_post_fs_data(void) {}\n#endif\n',
     marker="ksu_selinux_hide_handle_post_fs_data(void) {}")

# A2: USER_ARG_NULL must be a pointer when SUSFS is on (ksu_sulog_capture takes a
#     pointer there) and a value otherwise.
edit(f"{KSU}/sulog/event.c",
     "    #define USER_ARG_NULL user_arg_null_ptr()\n",
     "#ifdef CONFIG_KSU_SUSFS\n    #define USER_ARG_NULL user_arg_null_ptr()\n"
     "#else\n    #define USER_ARG_NULL (*user_arg_null_ptr())\n#endif\n",
     marker="#ifdef CONFIG_KSU_SUSFS\n    #define USER_ARG_NULL")

# ============================================================================
# PART B — SUSFS core (GKI source) + the GKI patch's fs hooks, fixed for 4.19
# ============================================================================

# B1: fsnotify changed handle_event(<=5.x) -> handle_inode_event(>=5.9). Provide
#     both forms for the sdcard-monitor callback + the ops field.
edit_re("fs/susfs.c",
    r'static int susfs_handle_sdcard_inode_event\(struct fsnotify_mark \*mark, u32 mask,\s*'
    r'struct inode \*inode, struct inode \*dir,\s*'
    r'const struct qstr \*file_name, u32 cookie\)\s*\{\s*'
    r'if \(!file_name \|\| file_name->len != 7 \|\|\s*memcmp\(file_name->name, "Android", 7\)\)\s*return 0;',
    '#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 9, 0)\n'
    'static int susfs_handle_sdcard_inode_event(struct fsnotify_mark *mark, u32 mask,\n'
    '\t\t\tstruct inode *inode, struct inode *dir,\n'
    '\t\t\tconst struct qstr *file_name, u32 cookie)\n'
    '#else\n'
    'static int susfs_handle_sdcard_inode_event(struct fsnotify_group *group,\n'
    '\t\t\tstruct inode *inode, u32 mask, const void *data, int data_type,\n'
    '\t\t\tconst unsigned char *file_name, u32 cookie,\n'
    '\t\t\tstruct fsnotify_iter_info *iter_info)\n'
    '#endif\n{\n'
    '#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 9, 0)\n'
    '\tif (!file_name || file_name->len != 7 || memcmp(file_name->name, "Android", 7))\n'
    '\t\treturn 0;\n'
    '#else\n'
    '\tif (!file_name || strlen(file_name) != 7 || memcmp(file_name, "Android", 7))\n'
    '\t\treturn 0;\n#endif',
    marker="KERNEL_VERSION(5, 9, 0)")
edit("fs/susfs.c",
     "\t.handle_inode_event = susfs_handle_sdcard_inode_event,",
     "#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 9, 0)\n"
     "\t.handle_inode_event = susfs_handle_sdcard_inode_event,\n#else\n"
     "\t.handle_event = susfs_handle_sdcard_inode_event,\n#endif",
     marker=".handle_event = susfs_handle_sdcard_inode_event,")

# B2: struct mount not in scope for the SUS_MOUNT extern in stat.c
edit("fs/stat.c",
     "#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\nextern int susfs_get_non_sus_mnt_id_from_mnt(struct mount *orig_mnt);\n#endif",
     "#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\nstruct mount;\nextern int susfs_get_non_sus_mnt_id_from_mnt(struct mount *orig_mnt);\n#endif",
     marker="struct mount;\nextern int susfs_get_non_sus_mnt_id_from_mnt")

# B3: 4.19 struct mount has no mnt_stuck_children; and copy_flags hunk misapplied
edit("fs/namespace.c", "\t\tINIT_HLIST_HEAD(&mnt->mnt_stuck_children);\n", "",
     marker="<<no-mnt_stuck_children>>", count=2)
edit("fs/namespace.c",
     "\tget_fs_root(current->fs, &fs_root);\n#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n\tcopy_flags |= CL_COPY_MNT_NS;\n#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n\n\tchrooted = !path_equal(&fs_root, &ns_root);",
     "\tget_fs_root(current->fs, &fs_root);\n\n\tchrooted = !path_equal(&fs_root, &ns_root);",
     marker="<<no-copy_flags-in-current_chrooted>>")

# B4: a SUS_PATH hunk fuzzed onto file scope; remove it (re-added correctly in B4b)
edit("fs/namei.c",
     "EXPORT_SYMBOL(hashlen_string);\n\n#ifdef CONFIG_KSU_SUSFS_SUS_PATH\n\t\tif (nd->state & ND_STATE_LOOKUP_LAST) {\n\t\t\tnd->flags |= ND_FLAGS_LOOKUP_LAST;\n\t\t}\n#endif\n",
     "EXPORT_SYMBOL(hashlen_string);\n",
     marker="<<no-misplaced-nd-state>>")

# B4b: re-add that SUS_PATH lookup-last hook at the correct site (walk_component,
#      just before lookup_slow). __lookup_slow reads flags & ND_FLAGS_LOOKUP_LAST.
edit("fs/namei.c",
     "\t\tif (err < 0)\n\t\t\treturn err;\n"
     "\t\tpath.dentry = lookup_slow(&nd->last, nd->path.dentry,\n"
     "\t\t\t\t\t  nd->flags);\n",
     "\t\tif (err < 0)\n\t\t\treturn err;\n"
     "#ifdef CONFIG_KSU_SUSFS_SUS_PATH\n"
     "\t\tif (nd->state & ND_STATE_LOOKUP_LAST)\n"
     "\t\t\tnd->flags |= ND_FLAGS_LOOKUP_LAST;\n"
     "#endif\n"
     "\t\tpath.dentry = lookup_slow(&nd->last, nd->path.dentry,\n"
     "\t\t\t\t\t  nd->flags);\n",
     marker="\t\t\tnd->flags |= ND_FLAGS_LOOKUP_LAST;")

# B5: 4.19 builds with -std=gnu89; move SUS_PATH decls above the first statement
edit("fs/readdir.c",
     "\tint error;\n\n\tif (!access_ok(VERIFY_WRITE, dirent, count))\n\t\treturn -EFAULT;\n"
     "#ifdef CONFIG_KSU_SUSFS_SUS_PATH\n\tint path_err = -EINVAL;\n\tstruct path path;\n#endif\n",
     "\tint error;\n#ifdef CONFIG_KSU_SUSFS_SUS_PATH\n\tint path_err = -EINVAL;\n\tstruct path path;\n#endif\n"
     "\n\tif (!access_ok(VERIFY_WRITE, dirent, count))\n\t\treturn -EFAULT;\n",
     marker="<<readdir-decls-moved>>", count=3)

# B6: port the /proc/<pid>/fdinfo mnt_id spoof to 4.19's simpler format (uses `mnt`)
edit("fs/proc/fd.c",
     '\tseq_printf(m, "pos:\\t%lli\\nflags:\\t0%o\\nmnt_id:\\t%i\\n",\n'
     '\t\t   (long long)file->f_pos, f_flags,\n'
     '\t\t   real_mount(file->f_path.mnt)->mnt_id);\n',
     '#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n'
     '\tmnt = real_mount(file->f_path.mnt);\n'
     '\tif (mnt->mnt_id >= DEFAULT_KSU_MNT_ID && likely(susfs_is_current_proc_umounted()))\n'
     '\t\tseq_printf(m, "pos:\\t%lli\\nflags:\\t0%o\\nmnt_id:\\t%i\\n",\n'
     '\t\t\t   (long long)file->f_pos, f_flags,\n'
     '\t\t\t   susfs_get_non_sus_mnt_id_from_mnt(mnt));\n'
     '\telse\n#endif\n'
     '\tseq_printf(m, "pos:\\t%lli\\nflags:\\t0%o\\nmnt_id:\\t%i\\n",\n'
     '\t\t   (long long)file->f_pos, f_flags,\n'
     '\t\t   real_mount(file->f_path.mnt)->mnt_id);\n',
     marker="susfs_get_non_sus_mnt_id_from_mnt(mnt));")

# B7: susfs_def.h uses current_uid() -> needs cred.h in TUs that include it early
edit("include/linux/susfs_def.h",
     "#ifndef KSU_SUSFS_DEF_H\n#define KSU_SUSFS_DEF_H\n",
     "#ifndef KSU_SUSFS_DEF_H\n#define KSU_SUSFS_DEF_H\n#include <linux/cred.h>\n",
     marker="#define KSU_SUSFS_DEF_H\n#include <linux/cred.h>")

# B8: GKI execve hook landed in 4.19 do_execve_file() which lacks fd/filename/...;
#     the __do_execve_file() hook (apply_ksu_hooks.py) already covers execve.
edit("fs/exec.c",
     '\tstruct user_arg_ptr argv = { .ptr.native = __argv };\n#ifdef CONFIG_KSU_SUSFS\n'
     '\tif (likely(susfs_is_current_proc_umounted()))\n\t\tgoto orig_flow;\n\n'
     '\tif (static_branch_likely(&ksu_su_compat_enabled)) {\n'
     '\t\tif (static_branch_unlikely(&susfs_is_sdcard_android_data_not_decrypted))\n'
     '\t\t\tksu_handle_execveat(&fd, &filename, &argv, &envp, &flags);\n'
     '\t\telse\n'
     '\t\t\tksu_handle_execveat_sucompat(&fd, &filename, &argv, &envp, &flags);\n'
     '\t}\n\norig_flow:\n#endif\n\n'
     '\tstruct user_arg_ptr envp = { .ptr.native = __envp };\n',
     '\tstruct user_arg_ptr argv = { .ptr.native = __argv };\n'
     '\tstruct user_arg_ptr envp = { .ptr.native = __envp };\n',
     marker="<<no-gki-execve-block>>")


# B9/B10: selinux_hide (fake selinux status) is GKI-only and uses 5.10
#         selinux_state internals -> guard all its blocks to >=5.10 so 4.19 takes
#         the original selinux paths.
def guard_selinux_hide(path):
    full = os.path.join(K, path)
    if not os.path.exists(full):
        print(f"[!] {path}: missing"); failed.append(path); return
    s = open(full).read()
    if "defined(CONFIG_KSU_SUSFS) && LINUX_VERSION_CODE" in s:
        print(f"[=] {path}: already guarded"); return
    if "#include <linux/version.h>" not in s:
        s = s.replace("#include <linux/kernel.h>\n",
                      "#include <linux/kernel.h>\n#include <linux/version.h>\n", 1)
    n = s.count("#ifdef CONFIG_KSU_SUSFS\n")
    s = s.replace("#ifdef CONFIG_KSU_SUSFS\n",
                  "#if defined(CONFIG_KSU_SUSFS) && LINUX_VERSION_CODE >= KERNEL_VERSION(5, 10, 0)\n")
    open(full, "w").write(s)
    print(f"[+] {path}: guarded {n} selinux_hide blocks")


guard_selinux_hide("security/selinux/selinuxfs.c")
guard_selinux_hide("security/selinux/hooks.c")

if failed:
    print(f"\nERROR: failed for: {failed}")
    sys.exit(1)
print("\nSUSFS 4.19 port applied successfully.")
