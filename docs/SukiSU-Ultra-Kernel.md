# 一加 8T (kebab) LineageOS 23.2 — SukiSU-Ultra Root 内核

本文档说明如何为 **一加 8T**（代号 `kebab`，sm8250 / kona，骁龙865）正在运行的
**LineageOS 23.2**（如 `23.2-20260626-NIGHTLY-kebab`）编译一个集成 **SukiSU-Ultra**
的内核（**4.19.325**），并刷入获取 root。

> 一加 8T 的内核是 **4.19（非 GKI）**。SukiSU / KernelSU **不为非 GKI 内核提供预编译
> boot 镜像**，因此必须自行编译内核——这正是本仓库提供脚本与 CI 的原因。

---

## 1. 原理简介

- 内核源码与你的 ROM 同源：`LineageOS/android_kernel_oneplus_sm8250` 的 `lineage-23.2`
  分支，版本正好是 **4.19.325**，刷入后与现有 LineageOS 兼容性最好。
- SukiSU-Ultra 以**内核内置驱动**（`drivers/kernelsu`）方式加入，并对内核打入
  **完整手动 syscall hook**（非 GKI 必需，不用 kprobe）：
  - `fs/exec.c`、`fs/open.c`（faccessat 同时是管理器通信通道）、`fs/read_write.c`、
    `fs/stat.c`、`drivers/input/input.c`（音量键 safe mode）。
  - 这些改动由 `scripts/apply_ksu_hooks.py` 自动、幂等地完成。
- 编译产物 `Image` 用 **AnyKernel3** 打包成刷机包，**只替换 boot 分区里的内核**，
  不动 ramdisk / vendor，所以 Wi‑Fi、音频等 vendor 模块（`.ko`）仍按原 vermagic 加载。

---

## 2. 两种编译方式（任选其一）

### 方式 A：GitHub Actions 云端编译（推荐，无需本地 Linux）

1. 把本仓库（含 `.github/workflows/build-sukisu-kernel.yml`）放到你自己的 GitHub 账号下。
2. 打开仓库 **Actions** → 选择 **Build SukiSU-Ultra Kernel (OnePlus 8T / kebab)** →
   **Run workflow**。可选项：
   - `enable_susfs`：是否集成 SUSFS（隐藏 root，过完整性校验），默认关。
   - `enable_kpm`：是否启用 SukiSU KPM，默认关。
   - `enable_lto`：是否启用 Clang LTO（更慢更吃内存），默认关。
   - `make_release`：是否把刷机包发布为 Release。
3. 等待编译完成（约 30–50 分钟），在该次运行的 **Artifacts**（或 Release）里下载
   `SukiSU-Ultra-kebab-4.19.325` 刷机包 zip。

### 方式 B：本地编译（自己的 Ubuntu/Linux）

```bash
# 依赖（Ubuntu/Debian）
sudo apt-get update
sudo apt-get install -y git curl zip bc bison flex libssl-dev libelf-dev cpio \
  kmod python3 build-essential libncurses-dev ccache clang lld llvm \
  binutils-aarch64-linux-gnu

# 在本仓库根目录执行
bash scripts/build-sukisu-kernel.sh
# 可选开关：
#   ENABLE_SUSFS=1 ENABLE_KPM=1 ENABLE_LTO=1 JOBS=8 bash scripts/build-sukisu-kernel.sh
```

脚本会自动：克隆内核 → 下载 **AOSP clang-r416183b** → 接入 SukiSU-Ultra → 打 hook →
按 `vendor/kona-perf_defconfig + vendor/oplus.config` 配置 → 编译 `Image` → 用
AnyKernel3 打包。完成后刷机包在 `kbuild/out_zip/` 下。

---

## 3. 刷入刷机包

一加 8T 是 **A/B 机型**。先**备份当前 boot**，再刷。

### 方法一：自定义 Recovery（最简单）
1. 安装 OrangeFox/TWRP（kebab 版）。
2. 进 Recovery → 安装 → 选择 `SukiSU-Ultra_kebab_4.19.325_*.zip` → 刷入 → 重启。

### 方法二：fastboot（无 TWRP 时）
AnyKernel3 zip 也支持把内核打进 boot 后用 fastboot 刷。或手动：
```bash
# 先备份当前槽位 boot（重要！）
adb reboot bootloader
# 用刷机包内的 AnyKernel3 直接生成/刷写，或自行用 magiskboot 把 Image 打进原 boot.img 后：
fastboot flash boot patched_boot.img      # 刷到当前使用的槽位
fastboot reboot
```
> 回退：重新刷入原始 boot（或重刷 LineageOS 整包 / `fastboot flash boot <原boot.img>`）。

---

## 4. 安装管理器并验证 root

1. 从 SukiSU-Ultra 的 GitHub Releases 下载 **管理器 APK** 并安装。
2. 打开管理器，应显示 **已安装 / Working**、内核版本 `4.19.325`、SukiSU 版本号。
3. 用任意需要 root 的 App（或终端 `su`）测试授权。

如启用了 **SUSFS**：在管理器内开启相应隐藏项后，用完整性检测类 App 验证。

---

## 5. 关键技术要点（排错必读）

这些是经过实测确认、容易踩坑的点：

| 项 | 说明 |
|---|---|
| **工具链** | 必须用内核 `build.config.common` 锁定的 **AOSP clang-r416183b (clang 12)**。更高版本 clang（13/18/19）会在高通 charger 等驱动上因 `-Werror`（implicit declaration / visibility）编译失败。 |
| **defconfig 两段** | 必须 `vendor/kona-perf_defconfig` + `vendor/oplus.config`（与 LineageOS `TARGET_KERNEL_CONFIG` 一致）。缺 `oplus.config` 会因 `__SMB5_CHARGER_H` 头文件保护宏冲突，使 `schgm-flash.c` 编译失败。 |
| **SukiSU 版本锁定** | `builtin`（non-GKI）分支 **HEAD 目前在 4.19 上编译失败**（`selinux_hide` 调用未对 <5.10 加保护、`USER_ARG_NULL` 传指针给传值参数）。脚本默认锁定到已知良好的提交 `04da52ef4a`（v4.1.3 基线）。上游修复后可用 `KSU_REF=` 覆盖。 |
| **hook 方式** | non-GKI + 32 位 userspace 用**完整手动 hook**，不用 kprobe（SukiSU 主线对 non-GKI 的 kprobe 标为不适用）。 |
| **主机工具链** | 编译用 `LLVM=1` 但主机工具走系统 LLVM（脚本 `PATH=/usr/bin:$PATH`）；否则旧工具链自带的 `ld.lld` 链接现代 glibc 会报 `.relr.dyn` 错误。 |
| **vendor 模块兼容** | 仅替换 `Image`，保持 `CONFIG_LOCALVERSION="-perf"` 与版本不变，vermagic 不变，原 ROM 的 `.ko` 仍可加载。若个别模块异常，回退原 boot。 |

---

## 6. FAQ

- **会不会变砖？** 只换内核、A/B 机型可回退；务必先备份当前 boot。刷错可重刷原 boot 或 ROM 整包。
- **OTA 升级后 root 没了？** LineageOS 升级会覆盖 boot，需要为新版本重新编译/刷入对应内核。
- **能直接用别人的 GKI 刷机包吗？** 不能。4.19 是非 GKI，必须针对本机/本 ROM 编译。
- **想要更强隐藏？** 用 `ENABLE_SUSFS=1` 重新编译并在管理器内配置 SUSFS。

---

## 参考
- 内核源码：https://github.com/LineageOS/android_kernel_oneplus_sm8250 （`lineage-23.2`）
- SukiSU-Ultra：https://github.com/SukiSU-Ultra/SukiSU-Ultra ｜ https://sukisu.org
- 非 GKI 集成说明：https://kernelsu.org/guide/how-to-integrate-for-non-gki.html
- SUSFS：https://gitlab.com/simonpunk/susfs4ksu
- AnyKernel3：https://github.com/osm0sis/AnyKernel3
