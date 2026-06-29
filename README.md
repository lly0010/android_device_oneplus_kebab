# 一加 8T (kebab) 预编译 boot.img — SukiSU-Ultra (LineageOS 23.2 / 4.19.325)

已编译好的 boot.img(gzip 压缩),**直接 fastboot 刷,不需要任何 recovery**。
基于官方 LineageOS kebab **20260626** 原厂 boot.img 换上自编译内核(ramdisk/dtb/cmdline 原样保留)。

> ⚠️ LineageOS 自带 recovery 刷不了 AnyKernel3 zip(签名校验),所以用这个 boot.img 方式。

## 文件(按推荐顺序)
- **`boot_SukiSU-SUSFS-KPM-FIXED_kebab_4.19.325.img.gz`** ⭐ **推荐**:SukiSU + SUSFS(隐藏 root/过完整性)+ KPM,
  **已修复**「管理器认不到 root」的 bug(根因:SUSFS 版误把自己标成 inline-hook,导致管理器走 reboot 系统调用被
  Android seccomp 沙箱拦截崩溃;改为如实上报 Manual Hook)。**要 SUSFS 就刷这个。**
- `boot_SukiSU-base_kebab_4.19.325.img.gz`:纯 SukiSU root,无 SUSFS。最稳、已实测可 root;不需要隐藏功能就用它。
- ~~`boot_SukiSU-SUSFS_kebab_4.19.325.img.gz` / `boot_SukiSU-SUSFS-KPM_kebab_4.19.325.img.gz`~~:
  旧 SUSFS 版,有上述「认不到 root」bug,**已被 FIXED 版取代,别用**。

## 用法
```bash
gunzip boot_SukiSU-SUSFS-KPM-FIXED_kebab_4.19.325.img.gz   # 解压(Windows 用 7-zip 也行)
adb reboot bootloader
fastboot boot boot_SukiSU-SUSFS-KPM-FIXED_kebab_4.19.325.img   # ① 零风险临时启动(不写盘)
#   进系统 + SukiSU 管理器显示已 root → 再永久刷:
fastboot flash boot boot_SukiSU-SUSFS-KPM-FIXED_kebab_4.19.325.img   # ②
fastboot reboot
```
卡开机就长按电源强制重启(`fastboot boot` 不写盘,无损)。回退:`fastboot flash boot <原厂 boot.img>`。
详见主分支 `docs/SukiSU-Ultra-Kernel.md`。
