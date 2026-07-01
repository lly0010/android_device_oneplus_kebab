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
   - `make_bootimg`：是否额外产出可 `fastboot flash boot` 直刷的 boot.img（默认开，**推荐**）。
   - `los_boot_url`：原厂 boot.img 地址（留空=自动取 LineageOS 最新 kebab 版）。
   - `make_release`：是否把刷机包发布为 Release。
3. 等待编译完成（约 30–50 分钟），在该次运行的 **Artifacts**（或 Release）里下载产物：
   `boot_*.img`（fastboot 直刷，**推荐**）和 `SukiSU-Ultra*_kebab_4.19.325_*.zip`（AnyKernel3）。

### 方式 B：本地编译（自己的 Ubuntu/Linux）

```bash
# 依赖（Ubuntu/Debian）
sudo apt-get update
sudo apt-get install -y git curl zip unzip bc bison flex libssl-dev libelf-dev cpio \
  kmod python3 build-essential libncurses-dev ccache clang lld llvm \
  binutils-aarch64-linux-gnu

# 在本仓库根目录执行
bash scripts/build-sukisu-kernel.sh
# 可选开关：
#   ENABLE_SUSFS=1 ENABLE_KPM=1 ENABLE_LTO=1 JOBS=8 bash scripts/build-sukisu-kernel.sh
```

脚本会自动：克隆内核 → 下载 **AOSP clang-r416183b** → 接入 SukiSU-Ultra → 打 hook →
按 `vendor/kona-perf_defconfig + vendor/oplus.config` 配置 → 编译 `Image` → 用
AnyKernel3 打包 → 再用 magiskboot 生成 `boot.img`。完成后产物在 `kbuild/out_zip/` 下
（`boot_*.img` 可 fastboot 直刷 + AnyKernel3 `*.zip`）。

---

## 3. 刷入（两种方式，推荐 boot.img）

一加 8T 是 **A/B 机型**。**刷前务必备份当前 boot**。

> ⚠️ **LineageOS 自带 recovery 刷不了 AnyKernel3 zip！** 它强制校验 OTA 签名，遇到未签名的
> AnyKernel3 包会报 `Signature verification failed` / `Install ... status 1 / aborted` 而中止
> （手机不会被改动）。所以要么用下面的 **boot.img 方式（不用 recovery）**，要么用
> **OrangeFox/TWRP** 刷 zip。

### 方式一：fastboot 直刷 boot.img（推荐，全程不碰 recovery）
构建会额外产出 `boot_SukiSU-Ultra*_kebab_4.19.325_*.img`（在 Actions 的 Artifacts / Release 里）。
它 = 官方 LineageOS kebab 原厂 `boot.img` 换上本内核（ramdisk/dtb/cmdline 原封不动），
由 `magiskboot` 在构建时完成，等价于 AnyKernel3 在机上做的事。

```bash
adb reboot bootloader
# ① 先零风险测试：临时启动（ramboot，不写入任何分区）
fastboot boot boot_SukiSU-Ultra_kebab_4.19.325_*.img
#    能进系统 + 管理器显示已 root → 再永久刷入：
# ② 永久刷入当前槽位
fastboot flash boot boot_SukiSU-Ultra_kebab_4.19.325_*.img
fastboot reboot
```
> 卡开机/黑屏？因 `fastboot boot` 不写盘，长按电源强制重启即恢复原状，毫发无损。
> 回退已刷入的：`fastboot flash boot <原厂 boot.img>`（LineageOS 下载页对每个版本都单独提供 boot.img）。

### 方式二：OrangeFox/TWRP 刷 AnyKernel3 zip
1. `adb reboot bootloader` → `fastboot boot OrangeFox-kebab.img`（临时启动，不必永久安装）。
2. 进去 → Install / ADB Sideload → 选 `SukiSU-Ultra*_kebab_4.19.325_*.zip` → 刷入 → 重启。
> **不要用 LineageOS 自带 recovery 的 “Apply update from ADB” 刷这个 zip**（签名校验会拒绝）。

---

## 4. 安装管理器并验证 root

1. 从 SukiSU-Ultra 的 GitHub Releases 下载 **管理器 APK** 并安装。
2. 打开管理器，应显示 **已安装 / Working**、内核版本 `4.19.325`、SukiSU 版本号。
3. 用任意需要 root 的 App（或终端 `su`）测试授权。

---

## 4b. SUSFS（隐藏 root，过完整性 / 银行检测）

上游只为 GKI(5.10+)提供 SukiSU 风味的 SUSFS；**本仓库已把它移植到 4.19**。开启：

```bash
ENABLE_SUSFS=1 bash scripts/build-sukisu-kernel.sh
# 或在 GitHub Actions 里勾上 enable_susfs
```

- **原理**：用 SukiSU `builtin` HEAD + ShirkNeko 的 GKI susfs 源码，由
  `scripts/apply_susfs_4.19_port.py` 自动打十几处 5.10→4.19 修正(fsnotify 回调、
  struct 字段、声明顺序、selinux_hide 版本守卫、SukiSU 驱动 2 个非 GKI bug 等)。
- **启用的隐藏功能**：SUS_PATH(藏文件)、SUS_MOUNT(藏挂载)、SUS_KSTAT(伪装 stat)、
  SPOOF_UNAME、SPOOF_CMDLINE、HIDE_KSU_SUSFS_SYMBOLS —— 过完整性检测够用。
- **已关闭(GKI 专属/4.19 不适用)**：OPEN_REDIRECT、SUS_MAP、selinux_hide。
- **⚠️ 重要**：SUSFS 版**仅编译验证、未在真机启动测试**，改的是 fs 敏感路径，有开机
  循环风险。刷前**务必备份 boot**；建议先 `fastboot boot <生成的boot>` 临时启动确认能
  进系统再正式刷。刷入后在 SukiSU 管理器里开启隐藏项，用完整性检测 App 验证。

---

## 5. 关键技术要点（排错必读）

这些是经过实测确认、容易踩坑的点：

| 项 | 说明 |
|---|---|
| **工具链** | 必须用内核 `build.config.common` 锁定的 **AOSP clang-r416183b (clang 12)**。更高版本 clang（13/18/19）会在高通 charger 等驱动上因 `-Werror`（implicit declaration / visibility）编译失败。 |
| **defconfig 两段** | 必须 `vendor/kona-perf_defconfig` + `vendor/oplus.config`（与 LineageOS `TARGET_KERNEL_CONFIG` 一致）。缺 `oplus.config` 会因 `__SMB5_CHARGER_H` 头文件保护宏冲突，使 `schgm-flash.c` 编译失败。 |
| **SukiSU 版本锁定** | 无 SUSFS 默认锁 `04da52ef4a`(v4.1.3 基线, 直接可编译)。HEAD 本身在 4.19 有 2 个编译 bug(`selinux_hide` 未对 <5.10 加保护、`USER_ARG_NULL` 类型);SUSFS 路径用 HEAD 并由 `apply_susfs_4.19_port.py` 一并修好。可 `KSU_REF=` 覆盖。 |
| **SUSFS 来源** | SukiSU 风味 susfs 上游**只做了 GKI**；本仓库用 ShirkNeko `gki-android12-5.10` 源码 + `apply_susfs_4.19_port.py` 移植到 4.19(约 95% 直接兼容)。OPEN_REDIRECT/SUS_MAP/selinux_hide 是 GKI 专属已关闭。 |
| **hook 方式** | non-GKI + 32 位 userspace 用**完整手动 hook**，不用 kprobe（SukiSU 主线对 non-GKI 的 kprobe 标为不适用）。 |
| **主机工具链** | 编译用 `LLVM=1` 但主机工具走系统 LLVM（脚本 `PATH=/usr/bin:$PATH`）；否则旧工具链自带的 `ld.lld` 链接现代 glibc 会报 `.relr.dyn` 错误。 |
| **vendor 模块兼容** | 仅替换 `Image`，保持 `CONFIG_LOCALVERSION="-perf"` 与版本不变，vermagic 不变，原 ROM 的 `.ko` 仍可加载。若个别模块异常，回退原 boot。 |

---

## 6. FAQ

- **会不会变砖？** 只换内核、A/B 机型可回退；务必先备份当前 boot。刷错可重刷原 boot 或 ROM 整包。
- **OTA 升级后 root 没了？** LineageOS 升级会覆盖 boot，需要为新版本重新编译/刷入对应内核。
- **能直接用别人的 GKI 刷机包吗？** 不能。4.19 是非 GKI，必须针对本机/本 ROM 编译。
- **想要过完整性 / 银行检测？** 用 `ENABLE_SUSFS=1` 重新编译（见 4b 节）并在管理器内配置 SUSFS。注意 SUSFS 版仅做了编译验证，需自行真机测试。

---

## 参考
- 内核源码：https://github.com/LineageOS/android_kernel_oneplus_sm8250 （`lineage-23.2`）
- SukiSU-Ultra：https://github.com/SukiSU-Ultra/SukiSU-Ultra ｜ https://sukisu.org
- 非 GKI 集成说明：https://kernelsu.org/guide/how-to-integrate-for-non-gki.html
- SUSFS（原版）：https://gitlab.com/simonpunk/susfs4ksu
- SUSFS（SukiSU 风味, 移植自此）：https://github.com/ShirkNeko/susfs4ksu （`gki-android12-5.10`）
- 移植脚本：`scripts/apply_susfs_4.19_port.py`（本仓库）
- AnyKernel3：https://github.com/osm0sis/AnyKernel3
