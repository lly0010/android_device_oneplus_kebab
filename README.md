# 一加 8T (kebab) 预编译 boot.img — SukiSU-Ultra (LineageOS 23.2 / 4.19.325)

已编译好的 boot.img(gzip 压缩),**直接 fastboot 刷,不需要任何 recovery**。
基于官方 LineageOS kebab **20260626** 原厂 boot.img 换上自编译内核(ramdisk/dtb/cmdline 原样保留)。

> ⚠️ LineageOS 自带 recovery 刷不了 AnyKernel3 zip(签名校验),所以用这个 boot.img 方式。

## 文件(按推荐顺序)
- **`boot_SukiSU-SUSFS-KPM-FIX2_kebab_4.19.325.img.gz`** ⭐ **推荐(要 SUSFS 刷这个)**:
  SukiSU + SUSFS(隐藏 root/过完整性)+ KPM。**修好了「管理器认不到 root」的真正根因**——
  SUSFS 版漏注册了解除管理器 seccomp 的 LSM `task_fix_setuid` 钩子,导致管理器 `reboot` supercall
  被 seccomp 杀;FIX2 给 SUSFS 也注册了该钩子。
- `boot_SukiSU-base_kebab_4.19.325.img.gz`:纯 SukiSU root,无 SUSFS。最稳、已实测可 root;不需要隐藏功能就用它。
- ~~其余 `boot_SukiSU-SUSFS*` / `*-FIXED*`~~:旧版,有 root 检测 bug,**已被 FIX2 取代,别用**。

## 用法
```bash
gunzip boot_SukiSU-SUSFS-KPM-FIX2_kebab_4.19.325.img.gz
adb reboot bootloader
fastboot boot boot_SukiSU-SUSFS-KPM-FIX2_kebab_4.19.325.img   # ① 零风险临时启动(不写盘)
#   进系统 + SukiSU 管理器显示已 root → 再永久刷:
fastboot flash boot boot_SukiSU-SUSFS-KPM-FIX2_kebab_4.19.325.img   # ②
fastboot reboot
```
卡开机就长按电源强制重启(`fastboot boot` 不写盘,无损)。回退:`fastboot flash boot <原厂 boot.img>`。
详见主分支 `docs/SukiSU-Ultra-Kernel.md`。
