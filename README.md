# 一加 8T (kebab) 预编译 boot.img — SukiSU-Ultra (LineageOS 23.2 / 4.19.325)

已编译好的 boot.img(gzip 压缩),**直接 fastboot 刷,不需要任何 recovery**。
基于官方 LineageOS kebab **20260626** 原厂 boot.img 换上自编译内核(ramdisk/dtb/cmdline 原样保留)。

> ⚠️ LineageOS 自带 recovery 刷不了 AnyKernel3 zip(签名校验),所以用这个 boot.img 方式。

## 文件
- `boot_SukiSU-base_kebab_4.19.325.img.gz` — **基础版**:纯 SukiSU root,无 SUSFS。**最稳,建议先刷这个确认能用**。
- `boot_SukiSU-SUSFS_kebab_4.19.325.img.gz` — **SUSFS 版(无 KPM)**:SukiSU + SUSFS 隐藏 root,不含 KPM。用于排查"全功能版没 root"是不是 KPM 引起的。
- `boot_SukiSU-SUSFS-KPM_kebab_4.19.325.img.gz` — **全功能版**:SukiSU + SUSFS(隐藏 root/过完整性)+ KPM。SUSFS 仅编译验证,需真机测试。

## 用法
```bash
gunzip boot_SukiSU-base_kebab_4.19.325.img.gz        # 先解压
adb reboot bootloader
fastboot boot boot_SukiSU-base_kebab_4.19.325.img    # ① 零风险临时启动测试(不写盘)
#   能进系统 + SukiSU 管理器显示已 root → 再永久刷:
fastboot flash boot boot_SukiSU-base_kebab_4.19.325.img   # ②
fastboot reboot
```
卡开机就长按电源强制重启(`fastboot boot` 不写盘,无损)。回退:`fastboot flash boot <原厂 boot.img>`。
详见主分支 `docs/SukiSU-Ultra-Kernel.md`。
