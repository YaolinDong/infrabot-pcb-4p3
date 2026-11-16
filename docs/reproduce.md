# 打开、核验与重新导出

## 本仓库能直接复现的检查

使用 Python 3.10+，不需要额外依赖：

```bash
python3 -B tools/verify.py
python3 -B -m unittest discover -s tests -v
```

验证器从当前仓库读取实际文件，检查公开清单的大小和 SHA-256、338 个原理图/PCB 引脚网络、105 颗 BOM/CPL 的集合及数量、器件中心/旋转/装配面，以及 Gerber ZIP 的必要图层。清单不引用私有路径或未交付的历史快照。

脚本仅只读解析原生文件，不调用 EDA、不修改设计、不下单。它不会根据 DRC=0 推断实物供电、机械净空、阻抗或功能通过。

## EDA 打开与原生检查

1. 打开 `hardware/infrabot_pcb_4p3/infrabot_pcb_4p3.eprj3`。原生工程在嘉立创 EDA 专业版 4.1.71 导出。首次在其他版本保存时建议保留原始副本。
2. 确认 PCB 文档为 `PCB1`。该工程子目录内仅有一个有效 `.epcb2`；不要在其中解包历史工程或放入相同 UUID 的 PCB 快照。
3. 如果 LED2 的 3D 模型未显示，按 `hardware/library/README.md` 导入和关联本地 STEP。该步骤仅影响模型展示，关联后仍应检查是否意外改动器件位置。
4. 从原理图核对网表，在 PCB 重建铺铜并保存；执行严格 DRC 和原理图 ERC。保留原始告警。已知例外见 `verification/README.md`，不能扩大到其他器件或错误。

本公开版未附 API 自动编辑/布局/布线脚本，也不要求安装专用桥接。可直接使用 EDA 界面执行原生检查及制造导出。

## 导出新版本

修改设计后，R8 的制造文件和哈希只是历史基准，不能与新源文件混用。

- 原生导出 Gerber，包含四个铜层、阻焊、丝印、顶面钢网、板框及 PTH/NPTH 钻孔。
- 原生导出完整 BOM 和坐标，使用 mm、同一板原点、TOP 装配面；确认每个器件的型号、Pin 1、旋转和 BOM/CPL 集合。
- 对照板厂和装配要求检查 LED2 成形脚、混合/直插件、最小钻孔和安装孔。
- 独立查看 Gerber 和顶/底视图，确认与源工程一致。
- 在新的版本目录保存导出和检查记录，制作完整的文件清单并运行离线验证；不要仅重算旧清单哈希来“放行”未经原生检查的新设计。

当前 `tools/verify.py` 明确检查 R8 及其预期网络。移植成其他硬件版本时需同步更改版本路径、预期网络、制造数据和检查依据，注明设计变化。

## 完整发布 ZIP

```bash
python3 -B tools/package_release.py
# 如默认文件已存在，可选择新文件名：
python3 -B tools/package_release.py --output .build/infrabot_r8_copy.zip
```

打包前必须通过离线检查；ZIP 包含当前公开源文件、制造资料、文档、许可与核验工具，并附 SHA-256。默认输出为 `.build/infrabot-pcb-4p3-R8.zip`，压缩包顶层目录为 `infrabot-pcb-4p3/`；`.build/` 被 Git 忽略。新机器解压后可运行相同命令核验，不依赖原作者电脑的缓存。

该 ZIP 可作为 GitHub Release 的附件；GitHub 仓库公开与否、远程地址和上传操作由仓库维护者设置。

## 原理图 PDF

英文首页为 `README.md`，中文入口为 `README.zh-CN.md`。`docs/schematics/` 提供六页矢量 PDF、原生 SVG 导出和对应来源清单；生成方法见该目录 README。PDF 构建依赖是可选项，不影响标准库离线核验。

## 原理图排布工具

`tools/layout_schematics.py --apply` 是本项目专用的排布工具。运行前关闭 EDA，运行后重新打开工程；不要让编辑器的旧缓存覆盖新文件。工具会先核对输入网络，再安排功能分区、符号和局部连线，写入前再次核对所有引脚网络。它不修改元件选型、封装或 PCB 布线。电路有意修改后应先更新设计与预期网络，不能借排版工具覆盖网络差异。整理后重新执行 EDA 原生 ERC、原生网表对照，并检查 PCB 关联元数据及严格 DRC。
