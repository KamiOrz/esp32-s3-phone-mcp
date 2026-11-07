# Phone MCP S3 集成板 — Rev A0 设计评审包

状态：原理图 A0 与 PCB 预布局已生成。原理图 ERC 通过；PCB 尚未布线，不是制造放行版，未输出 Gerber。
目标：替代 YD-ESP32-23 开发板及 Hub，单机连接一台已授权 USB 调试的安卓手机。
用户已确认：ESP32-S3 模组、一个电脑 Type-C 母座、一个手机 USB-A 母座、全贴片焊接。
本目录独立于被忽略的 hardware/，不含网络密码、ADB 私钥、令牌、PIN 或手机数据。

## 1. 架构

```text
现有：电脑 → 开发板 COM         拟设计：电脑 → J1 Type-C
              │                                  ├─USB2 D±→ESD→U2 CP2102N→UART0→U1
          S3 开发板                               ├─CC1/2→U3 TUSB320LAI→供电能力状态→U1
              │                                  └─VBUS→输入保护→5V_SYS
          Hub → 手机                                              ├─U4 Buck→3V3→U1等
                                                                  └─U5 限流/反向保护→J2 VBUS
                                           U1 原生USB GPIO19/20→ESD→J2 USB-A→手机
```

U1：ESP32-S3-WROOM-1-N16R8，保持现有 16MB Flash / 8MB PSRAM 配置。
USB Host 与电脑 USB 串口为两条独立的数据通道，禁止并联。
J2 D+/D- 不短接，不做充电专用口，不宣告快充。
首版不做 PD 高压请求；输入目标是 5V。

## 2. 供电约束与默认策略

电脑端 Type-C 插座不代表电脑必然提供 1.5A/3A。
U3 固定为 UFP/Sink，读取上游默认/1.5A/3A 宣告；不得再并联固定 Rd。
U5 EN 硬件下拉，上电、复位、未读到可靠供电能力时手机 VBUS 关闭。
首版手机端预算目标 500mA，连同主板留出余量，只在检测到至少 1.5A
Type-C 宣告、输入电压正常且固件准备好时使能。
不能把限流典型值当成保证值：需根据 TPS2553 限流上下限选择 RILIM，
当前手机支路 RILIM=44.2kΩ/1%，按厂家公式计算阈值约 531.8–658.8mA，支持500mA正常负载。
输入 eFuse 的 RILM=1.62kΩ/1%，典型阈值约1.25A。仍需验证短路、浪涌、手机电容与线损。
默认电流的老电脑 A 口首先用于刷机/调试；不保证可同时带手机。
USB 枚举前、挂起、掉电等功耗约束仍需在硬件/固件联调验证；
CC 检测本身不等于 USB 枚举授权，不作为 USB 合规结论。

输入保护须落实过压截止/电流限制与输入电容量约束，不能仅靠 TVS
代替过压保护，也不能把所有大电容直接挂在未受控输入 VBUS。
U5 只保护手机支路，不能代替整个板子的输入保护。
5V_SYS 与 PHONE_VBUS 分网；USB-A 端反向灌电不得回到电脑。

## 3. 模组连接分配（已与 KiCad 导出网表核对）

| 功能 | U1 信号 | 说明 |
|---|---|---|
| 手机 USB D- | GPIO19 | 串联阻值按官方指南/实测，靠模组 |
| 手机 USB D+ | GPIO20 | USB Full Speed 12Mbps，成对走线 |
| 烧录 UART TX | GPIO43/U0TXD | 接 U2 RXD |
| 烧录 UART RX | GPIO44/U0RXD | 接 U2 TXD，3.3V 逻辑 |
| 自动下载/复位 | GPIO0、EN | U2 DTR/RTS 经互锁双 NPN 电路；另保留 SMT BOOT/RESET |
| 手机电源开关 | GPIO4 | EN 下拉，启动默认关闭 |
| 手机过流故障 | GPIO5 | 开漏故障输入，3.3V 上拉 |
| CC I2C SDA/SCL | GPIO8/GPIO9 | 3.3V 上拉，确认 U3 上电时序/电平兼容 |
| 状态 LED | GPIO10 | 普通 LED 与串联限流电阻 |
| 预留检测 | GPIO6/GPIO7 | 输入/输出电压分压，防止掉电反供 |

不使用 GPIO35/36/37 等可能被 octal PSRAM 占用的脚。
EN 上拉、复位 RC、GPIO0 上拉与其他启动脚按模组资料审查。
保留 3V3/GND/EN/IO0/TX/RX、两侧 D±、5V_SYS/PHONE_VBUS 测试焊盘。

## 4. 初步机械约束

当前板框 55×35mm，已完成预布局，两接口同一边，便于单面外壳开孔。
模组天线位于相对一边，已外伸板边约6.5mm；组件总平面包络因此约55×41.5mm，不能把55×35mm当外壳内尺寸。外壳对应区域不得有金属/电池/螺柱。
模组天线实际禁布范围以官方封装与装壳射频验证为准。
2层、1.6mm FR4 为成本目标；若回流路径或电源布局不满足要求则改4层。
USB 阻抗按板厂实际叠层计算，不能预先随意指定线宽/间距。
器件尽量顶面贴装；电阻电容以0603为主，QFN/DFN器件采用回流焊。
定位孔、安装孔和过孔可以存在；全贴片指所有焊接引脚（含接口固定脚）为SMT。
外壳需承受USB插拔力，不让固定焊盘单独承力。

## 5. 全贴片器件初选

当前清单见 BOM.csv；BOM-candidates.csv 是最早的选型草案，不作为装配依据。
J1=USB4110-GF-A、J2=UJ2-AH-4-SMT-TR，已依据厂家图核对为全SMT焊接，
J2自建封装的两个1.3mm孔是塑料定位柱孔，不是焊接脚。
L1=XGL4020-472MEC，4.7uH，10%/20%/30%电感下降对应1.9/3.0/4.1A；
C23=T520D157M010ATE055，150uF/10V聚合物，正极接PHONE_VBUS。
U6=TPS259573DSGR，主动低电平OVLO型，不可直接换成同封装其他使能极性版本。
R/C等通用被动器件的具体采购品牌、直流偏压降容及供货仍需在装配BOM冻结时确认。
不能把库存库中“信号SMT、外壳THT”的USB-A母座当全贴片替代。

## 6. 固件影响

现有网络MCP、ADB与截图逻辑可以复用，但不是原固件原样烧录即可发布。
新增 board profile：启动读取CC、管理VBUS EN/故障、欠压关断、恢复状态机。
先检测供电再使能手机VBUS，最后启动USB Host；Wi-Fi状态服务不能无限等待USB枚举，
供电不足时也应能够报告状态。电脑USB默认电流模式需结合CP2102N配置与SUSPEND管脚，
核对枚举前电流、总线电流描述符和挂起策略；不能直接照搬现有固件启动顺序。
不再对USB错误无条件整板重启；电源切换应与USB Host状态同步。
保留本机独立ADB身份生成与本地配置，凭据不进入EDA文件或制造资料。

## 7. 放行检查

- 锁定全部精确MPN、封装焊盘、USB-A纯SMT版本和供货渠道。
- 核对官方参考电路、自动下载真值表与CP2102N VBUS检测分压。
- 电源预算、RILIM公差、输入保护、浪涌、挂起功耗、反灌审查。
- KiCad原理图/ERC、网表审查、PCB走线/DRC与原理图一致性。
- 输出装配图、BOM、坐标、Gerber、钻孔；审核前不称可直接生产。
- 实板验证烧录/Wi-Fi峰值/手机ADB/短路/掉电/重复插拔与连续运行。

## 8. 官方资料

- 模组：https://www.espressif.com/sites/default/files/documentation/esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf
- 设计指南：https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32s3/
- UART：https://www.silabs.com/documents/public/data-sheets/cp2102n-datasheet.pdf
- CP2102N VBUS：https://community.silabs.com/s/article/cp2102n-requires-a-voltage-divider-on-vbus?language=en_US
- CC：https://www.ti.com/lit/ds/symlink/tusb320lai.pdf
- 供电开关：https://www.ti.com/lit/ds/symlink/tps2553.pdf
- Buck：https://www.diodes.com/datasheet/download/AP63200-AP63201-AP63203-AP63205.pdf
- C口纯SMT：https://gct.co/files/info/gct-ionex-usb4110-product-release-booklet.pdf
- A口候选：https://www.sameskydevices.com/product/resource/uj2-ah-smt.pdf

## 9. 当前验证状态

已完成：86个原理图实例（含3个电源标志）、41个功能网络、234个引脚分配独立核对；
原理图ERC为0错误/0警告。PCB有67个贴装器件及16个测试焊盘；
当前几何违规0，原理图一致性差异0，但仍有197项未布线连接，PCB DRC不算通过。
全页自动视觉评分在重复标签匹配阶段耗时过长，已中断，未计为通过；已导出PDF/SVG供审阅。
尚未完成：PCB走线、USB阻抗/回流与电源开关环路复核、完整DRC、制造文件、固件适配及实板测试。
当前2层、1.6mm方案的USB线宽/间距未完成与板厂叠层的阻抗确认，不承诺90Ω。


## 10. 文件入口与重建

- phone-mcp-s3.kicad_pro：KiCad 10工程入口。
- phone-mcp-s3.kicad_sch：正式可编辑原理图（A0审阅版）。
- phone-mcp-s3.kicad_pcb：55×35mm预布局，未布线。
- review/phone-mcp-s3-schematic.pdf：原理图PDF。
- review/erc.rpt：原理图ERC；review/pcb-current/drc.rpt为JSON格式预布局检查。
- review/connectivity-check.json：独立网表检查及限流计算。
- review/STATUS.md：本次交付边界和待办。

项目生成器通过 `kicad-tool project-build` 调用结构化API；不要手工编辑EDA文件。
以下命令会按design.json重建A0，覆盖生成的原理图及PCB，手工继续布线前应另存版本。

```sh
python3 tools/make_spec.py
kicad-tool project-build tools/build_footprints.py --dry-run
kicad-tool project-build tools/build_footprints.py
kicad-tool project-build tools/build_design.py --dry-run
kicad-tool project-build tools/build_design.py
kicad-tool project-build tools/export_review.py
kicad-tool project-build tools/build_board.py --dry-run
kicad-tool project-build tools/build_board.py
python3 tools/configure_project.py
kicad-tool sch erc phone-mcp-s3.kicad_sch -o review/erc.rpt
```

生成器当前使用macOS的KiCad安装路径；工程文件可在安装标准库的其他KiCad 10平台打开。
厂家PDF保存在本机references/并被Git忽略，网络资料入口见上文。未把设计提交至在线EDA或云布线服务。
