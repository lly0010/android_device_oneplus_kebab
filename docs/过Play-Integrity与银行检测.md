# 一加 8T (kebab) — 过 Play Integrity / 银行检测

本文接续 [`SukiSU-Ultra-Kernel.md`](SukiSU-Ultra-Kernel.md)。**内核侧已完成**（SukiSU-Ultra root +
SUSFS 2.2.0：SUS_PATH / SUS_MOUNT / SUS_KSTAT + SPOOF_UNAME / SPOOF_CMDLINE +
HIDE_KSU_SUSFS_SYMBOLS），这是从内核层隐藏 root / 模块挂载 / KSU 痕迹的地基。过银行 /
完整性检测**剩下的全在手机上装模块 + 配置，不用再编内核**。

> ⚠️ 方法随 Google 服务端策略变化很快，本文为 **2026 年中**的有效方案；各模块请以其 GitHub 最新版为准。

---

## 1. 先对齐目标档位

Play Integrity 有三档，银行 / 支付通常只要前两档：

| 档位 | 含义 | 谁要求 | 你能否过 |
|---|---|---|---|
| **BASIC**（MEETS_BASIC_INTEGRITY） | 最低 | 几乎所有 | ✅ 稳过 |
| **DEVICE**（MEETS_DEVICE_INTEGRITY） | “正常 Android 设备” | 多数银行 / 支付 / Google Wallet 基础 | ✅ 稳过（靠 PIFork） |
| **STRONG**（MEETS_STRONG_INTEGRITY） | 硬件 TEE 认证 | 少数强检测银行 / Google Pay NFC | ⚠️ 需未吊销 keybox，不保证 |

> **现实预期**：你是骁龙 865、**非 GKI 4.19**、LineageOS（第三方 ROM）+ bootloader 已解锁。
> BASIC + DEVICE 稳过（覆盖绝大多数）；STRONG 靠共享 keybox，Google 会吊销，不保证长期。

---

## 2. 需要装的模块（2026 年中）

1. **ReZygisk**（或 NeoZygisk）—— Zygisk 提供者，PIFork / Shamiko 靠它运行。
   （SukiSU-Ultra 亦有内置 meta-module 可直接跑 PIFork，但装 ReZygisk 更通用、还能跑 Shamiko / LSPosed。）
2. **PlayIntegrityFork**（`osm0sis/PlayIntegrityFork`，2026-06 仍更新）—— **核心**，伪造设备指纹过 BASIC + DEVICE。
3. *(可选，仅 STRONG)* **TrickyStore** + **YuriKey Keybox Manager** —— 伪造 locked bootloader + keybox。
4. *(可选，建议)* **Hide My Applist (HMA)** —— 对银行 App 隐藏你装的 root 相关 App。

---

## 3. 分步操作

### 第 0 步 · 永久刷入内核（若还在 `fastboot boot` 临时状态）
```bash
fastboot flash boot boot_SukiSU-Ultra_SUSFS_kebab_4.19.325_*.img
fastboot reboot
```

### 第 1 步 · SukiSU 管理器配隐藏 + 卸载名单
1. 若有 **Zygisk 开关**先开（没有则靠第 2 步 ReZygisk）。
2. **卸载名单 / DenyList**：把**银行 App、Google Play 服务、Play 商店**加进“需要 umount 模块挂载”的名单
   → 它们就看不到模块 overlay。
3. **隐藏管理器**：开随机包名 / 改名 / 隐藏图标，别让银行按 `com.sukisu.ultra` 点名。

### 第 2 步 · 装 ReZygisk
GitHub Releases 下最新 zip → 管理器 → 模块 → 从本地安装 → 重启 → 确认已启用。

### 第 3 步 · 装 PlayIntegrityFork（核心）
1. `github.com/osm0sis/PlayIntegrityFork` Releases 下最新 zip → 安装。
2. **刷新指纹（关键）**：PIFork 靠一份被 Google 认证过的指纹（`pif.json`）过 DEVICE。它自带
   `autopif` 能自动抓新鲜可用指纹。**但 SukiSU 的 Action 按钮有 10 秒上限**，autopif 联网可能超时，两个办法：
   - a) 网络好时用管理器 **Action** 跑一次；或
   - b) 电脑 `adb shell` 手动跑模块里的 `autopif`（不受 10 秒限），或手动放一份 `pif.json` 进
     `/data/adb/modules/playintegrityfork/`。
3. 重启。

### 第 4 步 · 清缓存 + 验证
1. 设置 → 应用 → **Google Play 服务 → 存储 → 清除缓存**（只清缓存，别清数据；必要时 Play 商店同样清）。
2. 装 **Play Integrity API Checker** → 跑一次 → 期望 **BASIC ✅ + DEVICE ✅**（没配 TrickyStore 时 STRONG ❌ 正常）。
3. 打开银行 App 测试。**多数到这步即可用。**

### 第 5 步（可选，银行仍拦 / 要 STRONG）· TrickyStore + keybox
1. 装 **TrickyStore** + **YuriKey Keybox Manager**，重启。
2. YuriKey → Module 区 → YuriKey Keybox Manager → **Action** 自动拉取最新 `keybox.xml`。
3. 编辑 `/data/adb/tricky_store/target.txt` 把银行 / GMS 包名加进去；`<A13 STRONG` 时高级设置把
   **spoofProvider 关掉**。重启 → 再验 STRONG。
   > ⚠️ keybox 是共享的、会被 Google 吊销，STRONG 可能今天过明天不过；**DEVICE 才是稳的。**

### 第 6 步（可选）· HMA 藏 App
装 **Hide My Applist** → 对银行隐藏 SukiSU 管理器、检测器等 root 相关 App。

---

## 4. 排错

- **DEVICE 过不了**：指纹过期 → 重跑 `autopif` 换新指纹 / 换社区在用的 `pif.json` → 清 GMS 缓存重试。
- **装模块后 bootloop**：SUSFS 版动了 fs 敏感路径 + Zygisk 注入，可能冲突 → 进 fastboot
  `fastboot flash boot <可用 boot.img>` 回退，**一次只装一个模块**排查。
- **银行仍报 root**：确认它已进 SukiSU umount 名单 + HMA 名单；管理器包名已隐藏；个别银行还查
  bootloader 解锁（需 TrickyStore 伪装 locked）。

---

## 5. 现实边界（直说）

- BASIC / DEVICE：这套**稳过**，覆盖绝大多数银行、支付、Google Wallet 基础。
- STRONG：靠共享 keybox，**不保证长期**；Google 持续吊销。
- bootloader 解锁 + 第三方 ROM 属“尽量藏”而非“物理合规”；个别自研加固的银行（尤其国内某些）
  可能仍拦，那是它单独适配的事，非本方案能 100% 保证。

---

## 参考

- PlayIntegrityFork：https://github.com/osm0sis/PlayIntegrityFork
- PIFork（KernelSU Modules）：https://modules.kernelsu.org/module/playintegrityfix/
- TrickyStore（KernelSU Modules）：https://modules.kernelsu.org/module/tricky_store/
- ReZygisk：https://github.com/PerformanC/ReZygisk
- 过 STRONG Integrity 指南（XDA）：https://xdaforums.com/t/guide-how-to-pass-strong-integrity-on-android-step-by-step-guide.4729435/
