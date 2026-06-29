#!/usr/bin/env bash
#
# build-sukisu-kernel.sh
# 为一加 8T (kebab / sm8250 / kona) 编译带 SukiSU-Ultra root 的 LineageOS 23.2 内核 (4.19.325)
# 并打包成可刷入的 AnyKernel3 刷机包。
#
# 用法:
#   bash scripts/build-sukisu-kernel.sh
#
# 常用可调环境变量 (全部可选, 见下方默认值):
#   ENABLE_SUSFS=1     集成 SUSFS (隐藏 root, 过完整性校验)，默认 0
#   ENABLE_KPM=1       启用 SukiSU KPM，默认 0
#   ENABLE_LTO=1       启用 Clang LTO (更慢/更吃内存, 贴近 LineageOS 发行版)，默认 0
#   JOBS=8             并行编译任务数，默认 = nproc
#   CLANG_DIR=/path    使用已有的 clang-r416183b，跳过下载
#   KSU_REF=<commit>   覆盖 SukiSU-Ultra 提交 (默认按是否开 SUSFS 自动选 稳定/HEAD)
#
# 经过实测的关键点 (改动需谨慎):
#   * 内核必须用 AOSP clang-r416183b (内核 build.config.common 锁定的版本)。
#     更高版本 clang(13/18/19) 会在高通 charger 等驱动上因 -Werror 编译失败。
#   * defconfig 必须是两段: vendor/kona-perf_defconfig + vendor/oplus.config
#     (LineageOS TARGET_KERNEL_CONFIG 即如此)。缺少 oplus.config 会触发
#     __SMB5_CHARGER_H 头文件保护宏冲突，导致 schgm-flash.c 编译失败。
#   * non-GKI 走完整手动 hook (apply_ksu_hooks.py)，不是 kprobe。
#   * ENABLE_SUSFS=1: 用 SukiSU builtin HEAD + 把 ShirkNeko 的 GKI susfs 移植到 4.19
#     (apply_susfs_4.19_port.py)。核心隐藏 sus_path/mount/kstat/uname/cmdline 生效;
#     OPEN_REDIRECT/SUS_MAP/selinux_hide 是 GKI 专属已关闭。仅编译验证, 需真机测试。
#
set -euo pipefail

# ----------------------------------------------------------------------------
# 配置 (可用环境变量覆盖)
# ----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKDIR="${WORKDIR:-$(pwd)/kbuild}"

KERNEL_REPO="${KERNEL_REPO:-https://github.com/LineageOS/android_kernel_oneplus_sm8250}"
KERNEL_BRANCH="${KERNEL_BRANCH:-lineage-23.2}"
DEFCONFIG="${DEFCONFIG:-vendor/kona-perf_defconfig vendor/oplus.config}"

KSU_REPO="${KSU_REPO:-https://github.com/SukiSU-Ultra/SukiSU-Ultra}"
KSU_BRANCH="${KSU_BRANCH:-builtin}"          # builtin = non-GKI 分支

ANYKERNEL_REPO="${ANYKERNEL_REPO:-https://github.com/osm0sis/AnyKernel3}"

# AOSP clang-r416183b (内核锁定版本)
CLANG_GIT="https://android.googlesource.com/platform/prebuilts/clang/host/linux-x86"
CLANG_REF="${CLANG_REF:-0da2d994ef8c5c4d833b51c781cba4f2fa4d2721}"  # android12-d1-release，含 clang-r416183b
CLANG_NAME="clang-r416183b"

ENABLE_SUSFS="${ENABLE_SUSFS:-0}"
ENABLE_KPM="${ENABLE_KPM:-0}"
ENABLE_LTO="${ENABLE_LTO:-0}"
JOBS="${JOBS:-$(nproc)}"
OUTDIR="${OUTDIR:-$WORKDIR/out_zip}"

# SukiSU 提交: 无 SUSFS 用稳定基线; 带 SUSFS 用已实测移植的 builtin HEAD
if [ "$ENABLE_SUSFS" = "1" ]; then
  KSU_REF="${KSU_REF:-b88403d2561b6e00dff84a3c851e630c62f57fd0}"   # SukiSU builtin HEAD (实测移植)
else
  KSU_REF="${KSU_REF:-04da52ef4a}"                                  # v4.1.3 基线 (non-GKI 稳定)
fi

# SUSFS 源 = SukiSU 作者(ShirkNeko)的 GKI susfs, 由 apply_susfs_4.19_port.py 移植到 4.19
SUSFS_REPO="${SUSFS_REPO:-https://github.com/ShirkNeko/susfs4ksu}"
SUSFS_BRANCH="${SUSFS_BRANCH:-gki-android12-5.10}"
SUSFS_REF="${SUSFS_REF:-4003ecf2d01c6d13fa8edf6c4f2607365738dc3d}"
SUSFS_TAG=""; [ "$ENABLE_SUSFS" = "1" ] && SUSFS_TAG="_SUSFS"

log() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

# ----------------------------------------------------------------------------
log "工作目录: $WORKDIR"
mkdir -p "$WORKDIR"; cd "$WORKDIR"

# ----------------------------------------------------------------------------
log "1/8 克隆内核源码 ($KERNEL_BRANCH)"
if [ ! -d kernel/.git ]; then
  rm -rf kernel
  git clone --depth=1 -b "$KERNEL_BRANCH" "$KERNEL_REPO" kernel
fi
grep -qE '^SUBLEVEL = 325' kernel/Makefile || log "提示: 内核 SUBLEVEL 非 325，分支可能已更新"

# ----------------------------------------------------------------------------
log "2/8 准备工具链 clang-r416183b"
if [ -n "${CLANG_DIR:-}" ]; then
  CLANG_BIN="$CLANG_DIR/bin"
elif [ -x "$WORKDIR/aosp-clang/$CLANG_NAME/bin/clang" ]; then
  CLANG_BIN="$WORKDIR/aosp-clang/$CLANG_NAME/bin"
else
  rm -rf aosp-clang
  git clone --depth=1 --filter=blob:none --sparse "$CLANG_GIT" aosp-clang
  ( cd aosp-clang
    git fetch --depth=1 --filter=blob:none origin "$CLANG_REF"
    git sparse-checkout set "$CLANG_NAME"
    git checkout "$CLANG_REF" )
  CLANG_BIN="$WORKDIR/aosp-clang/$CLANG_NAME/bin"
fi
"$CLANG_BIN/clang" --version | head -1

# ----------------------------------------------------------------------------
log "3/8 集成 SukiSU-Ultra 驱动 (non-GKI builtin, 锁定 $KSU_REF)"
cd "$WORKDIR/kernel"
if [ ! -d KernelSU/.git ]; then
  rm -rf KernelSU
  git clone -b "$KSU_BRANCH" "$KSU_REPO" KernelSU
  git -C KernelSU checkout "$KSU_REF"
fi
# 等价于 setup.sh: 把驱动接入 drivers/
ln -sf ../KernelSU/kernel drivers/kernelsu
grep -q 'kernelsu' drivers/Makefile || echo 'obj-$(CONFIG_KSU) += kernelsu/' >> drivers/Makefile
grep -q 'kernelsu' drivers/Kconfig  || sed -i '/^menu "Device Drivers"/a source "drivers/kernelsu/Kconfig"' drivers/Kconfig
[ -e drivers/kernelsu/Kconfig ] || die "drivers/kernelsu 符号链接未解析"

# ----------------------------------------------------------------------------
log "4/8 应用 non-GKI 完整手动 hook"
python3 "$SCRIPT_DIR/apply_ksu_hooks.py" "$WORKDIR/kernel"

# ----------------------------------------------------------------------------
if [ "$ENABLE_SUSFS" = "1" ]; then
  log "4b/8 集成 SUSFS (SukiSU 风味, 从 GKI 移植到 4.19)"
  cd "$WORKDIR"
  if [ ! -d susfs4ksu/.git ]; then
    git clone -b "$SUSFS_BRANCH" "$SUSFS_REPO" susfs4ksu
    git -C susfs4ksu checkout "$SUSFS_REF"
  fi
  cd "$WORKDIR/kernel"
  SP=../susfs4ksu/kernel_patches
  cp "$SP/fs/susfs.c" fs/
  cp "$SP/include/linux/susfs.h" "$SP/include/linux/susfs_def.h" include/linux/
  # GKI susfs 补丁 (~90% 命中, 自动给 fs/Makefile 加 susfs.o; 余下不兼容处由移植脚本修)
  patch -p1 --forward --fuzz=3 --no-backup-if-mismatch \
    < "$SP/50_add_susfs_in_${SUSFS_BRANCH}.patch" || true
  find . -name '*.rej' -delete
  # 关键: 把 SukiSU 风味 susfs 移植到 4.19 (十几处 5.10->4.19 修正 + SukiSU 驱动 2 个非 GKI bug)
  python3 "$SCRIPT_DIR/apply_susfs_4.19_port.py" "$WORKDIR/kernel"
fi

# ----------------------------------------------------------------------------
if [ "$ENABLE_KPM" = "1" ]; then
  log "4c/8 KPM: 给 kpm.c 打 4.19 access_ok 兼容垫片 (5.0+ 2 参 -> 4.19 3 参)"
  python3 - "$WORKDIR/kernel/KernelSU/kernel/kpm/kpm.c" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
if '__kpm_access_ok' not in s:
    shim = ('#include <linux/version.h>\n#if LINUX_VERSION_CODE < KERNEL_VERSION(5, 0, 0)\n'
            'static inline int __kpm_access_ok(const void __user *a, unsigned long n)\n'
            '{ return access_ok(VERIFY_WRITE, a, n); }\n'
            '#pragma push_macro("access_ok")\n#undef access_ok\n'
            '#define access_ok(a, n) __kpm_access_ok((a), (n))\n#endif\n')
    anc = '#include <linux/uaccess.h>\n'
    assert anc in s, "kpm.c: uaccess.h anchor missing"
    s = s.replace(anc, anc + shim, 1)
    s = s.rstrip('\n') + '\n\n#if LINUX_VERSION_CODE < KERNEL_VERSION(5, 0, 0)\n#pragma pop_macro("access_ok")\n#endif\n'
    open(p, 'w').write(s); print('[+] kpm.c access_ok shim')
else:
    print('[=] kpm.c shim present')
PY
fi

# ----------------------------------------------------------------------------
log "5/8 生成内核配置 (kona-perf_defconfig + oplus.config + KSU)"
AOSP_CLANG="$CLANG_BIN/clang"
export PATH="/usr/bin:$PATH"   # 主机工具用系统 LLVM，避免旧工具链链接现代 glibc 失败
MK=(make -s O=out ARCH=arm64 LLVM=1 LLVM_IAS=1 "CC=$AOSP_CLANG")
rm -rf out
# shellcheck disable=SC2086
"${MK[@]}" $DEFCONFIG
CFG=(./scripts/config --file out/.config -e KSU)
if [ "$ENABLE_SUSFS" = "1" ]; then
  CFG+=(-e KSU_SUSFS -e KSU_SUSFS_SUS_PATH -e KSU_SUSFS_SUS_MOUNT -e KSU_SUSFS_SUS_KSTAT
        -e KSU_SUSFS_SPOOF_UNAME -e KSU_SUSFS_ENABLE_LOG -e KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG
        -e KSU_SUSFS_HIDE_KSU_SUSFS_SYMBOLS
        -d KSU_SUSFS_OPEN_REDIRECT -d KSU_SUSFS_SUS_MAP)   # 后两者 GKI 专属, 4.19 关闭
else
  CFG+=(-d KSU_SUSFS)
fi
[ "$ENABLE_KPM" = "1" ] && CFG+=(-e KPM) || CFG+=(-d KPM)
[ "$ENABLE_LTO" = "1" ] && CFG+=(-e LTO_CLANG) || CFG+=(-d LTO_CLANG -d LTO_CLANG_THIN -e LTO_NONE)
"${CFG[@]}"
"${MK[@]}" olddefconfig
grep -q '^CONFIG_KSU=y' out/.config || die "CONFIG_KSU 未启用"

# ----------------------------------------------------------------------------
log "6/8 编译内核 Image (-j$JOBS)"
"${MK[@]}" -j"$JOBS" Image
IMG="$WORKDIR/kernel/out/arch/arm64/boot/Image"
[ -f "$IMG" ] || die "未生成 Image"
log "Image 完成: $(ls -lh "$IMG" | awk '{print $5}')"

# ----------------------------------------------------------------------------
log "7/8 用 AnyKernel3 打包"
cd "$WORKDIR"
[ -d AnyKernel3/.git ] || git clone --depth=1 "$ANYKERNEL_REPO" AnyKernel3
cp -f "$IMG" AnyKernel3/Image
cat > AnyKernel3/anykernel.sh <<'AK'
properties() { '
kernel.string=SukiSU-Ultra kebab (OnePlus 8T) LineageOS 23.2 4.19.325
do.devicecheck=1
do.modules=0
do.systemless=1
do.cleanup=1
do.cleanuponabort=1
device.name1=kebab
device.name2=OnePlus8T
device.name3=OnePlus 8T
supported.versions=
supported.patchlevels=
'; }
block=/dev/block/bootdevice/by-name/boot
is_slot_device=1
ramdisk_compression=auto
patch_vbmeta_flag=auto
. tools/ak3-core.sh
split_boot
flash_boot
AK
sed -i "s|^kernel.string=.*|kernel.string=SukiSU-Ultra${SUSFS_TAG} kebab (OnePlus 8T) LineageOS 23.2 4.19.325|" AnyKernel3/anykernel.sh

# ----------------------------------------------------------------------------
log "8/8 生成刷机包"
mkdir -p "$OUTDIR"
ZIP="$OUTDIR/SukiSU-Ultra${SUSFS_TAG}_kebab_4.19.325_$(date +%Y%m%d-%H%M).zip"
( cd AnyKernel3 && zip -r9 "$ZIP" . -x '.git/*' 'README.md' '*.zip' >/dev/null )
log "完成! 刷机包: $ZIP"
ls -lh "$ZIP"
