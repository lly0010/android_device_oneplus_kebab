#!/usr/bin/env python3
# Applies SukiSU-Ultra / KernelSU non-GKI manual syscall hooks to a 4.19 kernel
# tree (OnePlus sm8250 / kona, LineageOS). Idempotent and anchor-based: it
# verifies each anchor is present and unique before editing, and is a no-op if
# the hook is already present.
import os
import sys

KROOT = sys.argv[1] if len(sys.argv) > 1 else "."
failed = False


def patch(path, old, new, marker):
    global failed
    full = os.path.join(KROOT, path)
    with open(full, "r") as f:
        s = f.read()
    if marker in s:
        print(f"[=] {path}: already hooked")
        return
    n = s.count(old)
    if n != 1:
        print(f"[!] {path}: anchor count = {n} (expected 1) -- NOT applied")
        failed = True
        return
    s = s.replace(old, new, 1)
    with open(full, "w") as f:
        f.write(s)
    print(f"[+] {path}: hook applied")


# 1) fs/exec.c -- execve hook in __do_execve_file()
patch(
    "fs/exec.c",
    "static int __do_execve_file(int fd, struct filename *filename,",
    "#ifdef CONFIG_KSU\n"
    "extern int ksu_handle_execveat(int *fd, struct filename **filename_ptr,\n"
    "\t\t\t       void *argv, void *envp, int *flags);\n"
    "#endif\n"
    "static int __do_execve_file(int fd, struct filename *filename,",
    "ksu_handle_execveat(&fd, &filename",
)
patch(
    "fs/exec.c",
    "\tif (IS_ERR(filename))\n"
    "\t\treturn PTR_ERR(filename);\n"
    "\n"
    "\t/*\n"
    "\t * We move the actual failure in case of RLIMIT_NPROC excess",
    "\tif (IS_ERR(filename))\n"
    "\t\treturn PTR_ERR(filename);\n"
    "\n"
    "#ifdef CONFIG_KSU\n"
    "\tif (filename)\n"
    "\t\tksu_handle_execveat(&fd, &filename, &argv, &envp, &flags);\n"
    "#endif\n"
    "\n"
    "\t/*\n"
    "\t * We move the actual failure in case of RLIMIT_NPROC excess",
    "ksu_handle_execveat(&fd, &filename, &argv",
)

# 2) fs/open.c -- faccessat hook (also the manager command channel)
patch(
    "fs/open.c",
    "long do_faccessat(int dfd, const char __user *filename, int mode)\n{",
    "#ifdef CONFIG_KSU\n"
    "extern int ksu_handle_faccessat(int *dfd, const char __user **filename_user,\n"
    "\t\t\t\tint *mode, int *flags);\n"
    "#endif\n"
    "long do_faccessat(int dfd, const char __user *filename, int mode)\n{",
    "ksu_handle_faccessat(&dfd, &filename",
)
patch(
    "fs/open.c",
    "\tunsigned int lookup_flags = LOOKUP_FOLLOW;\n"
    "\n"
    "\tif (mode & ~S_IRWXO)\t/* where's F_OK, X_OK, W_OK, R_OK? */\n"
    "\t\treturn -EINVAL;",
    "\tunsigned int lookup_flags = LOOKUP_FOLLOW;\n"
    "\n"
    "#ifdef CONFIG_KSU\n"
    "\tksu_handle_faccessat(&dfd, &filename, &mode, NULL);\n"
    "#endif\n"
    "\n"
    "\tif (mode & ~S_IRWXO)\t/* where's F_OK, X_OK, W_OK, R_OK? */\n"
    "\t\treturn -EINVAL;",
    "ksu_handle_faccessat(&dfd, &filename, &mode",
)

# 3) fs/read_write.c -- vfs_read hook (ksud trigger)
patch(
    "fs/read_write.c",
    "ssize_t vfs_read(struct file *file, char __user *buf, size_t count, loff_t *pos)\n"
    "{\n"
    "\tssize_t ret;\n"
    "\n"
    "\tif (!(file->f_mode & FMODE_READ))",
    "#ifdef CONFIG_KSU\n"
    "extern int ksu_handle_vfs_read(struct file **file_ptr, char __user **buf_ptr,\n"
    "\t\t\t       size_t *count_ptr, loff_t **pos);\n"
    "#endif\n"
    "ssize_t vfs_read(struct file *file, char __user *buf, size_t count, loff_t *pos)\n"
    "{\n"
    "\tssize_t ret;\n"
    "\n"
    "#ifdef CONFIG_KSU\n"
    "\tksu_handle_vfs_read(&file, &buf, &count, &pos);\n"
    "#endif\n"
    "\n"
    "\tif (!(file->f_mode & FMODE_READ))",
    "ksu_handle_vfs_read(&file, &buf",
)

# 4) fs/stat.c -- stat hook
patch(
    "fs/stat.c",
    "int vfs_statx(int dfd, const char __user *filename, int flags,\n"
    "\t      struct kstat *stat, u32 request_mask)\n"
    "{\n"
    "\tstruct path path;\n"
    "\tint error = -EINVAL;\n"
    "\tunsigned int lookup_flags = LOOKUP_FOLLOW | LOOKUP_AUTOMOUNT;\n",
    "#ifdef CONFIG_KSU\n"
    "extern int ksu_handle_stat(int *dfd, const char __user **filename_user, int *flags);\n"
    "#endif\n"
    "int vfs_statx(int dfd, const char __user *filename, int flags,\n"
    "\t      struct kstat *stat, u32 request_mask)\n"
    "{\n"
    "\tstruct path path;\n"
    "\tint error = -EINVAL;\n"
    "\tunsigned int lookup_flags = LOOKUP_FOLLOW | LOOKUP_AUTOMOUNT;\n"
    "\n"
    "#ifdef CONFIG_KSU\n"
    "\tksu_handle_stat(&dfd, &filename, &flags);\n"
    "#endif\n",
    "ksu_handle_stat(&dfd, &filename",
)

# 5) drivers/input/input.c -- input hook (safe mode via volume keys)
patch(
    "drivers/input/input.c",
    "static void input_handle_event(struct input_dev *dev,\n"
    "\t\t\t       unsigned int type, unsigned int code, int value)\n"
    "{\n"
    "\tint disposition = input_get_disposition(dev, type, code, &value);",
    "#ifdef CONFIG_KSU\n"
    "extern int ksu_handle_input_handle_event(unsigned int *type, unsigned int *code, int *value);\n"
    "#endif\n"
    "static void input_handle_event(struct input_dev *dev,\n"
    "\t\t\t       unsigned int type, unsigned int code, int value)\n"
    "{\n"
    "\tint disposition;\n"
    "\n"
    "#ifdef CONFIG_KSU\n"
    "\tksu_handle_input_handle_event(&type, &code, &value);\n"
    "#endif\n"
    "\n"
    "\tdisposition = input_get_disposition(dev, type, code, &value);",
    "ksu_handle_input_handle_event(&type, &code, &value)",
)

if failed:
    print("\nERROR: one or more hooks failed to apply.")
    sys.exit(1)
print("\nAll manual hooks applied successfully.")
