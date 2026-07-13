#!/usr/bin/env python3
"""
AutoCAD MCP Server — 通过 COM 接口控制 AutoCAD 配置的工具集。
MCP 协议 (stdio JSON-RPC)，可用作 Claude Code / Claude Desktop 的 MCP 服务器。

功能:
- 图层管理 (CRUD + 批量 + GB/T 预设)
- 文字样式 / 标注样式管理
- 线型加载
- 系统变量读写
- 图纸信息查询
"""

import json
import sys
import traceback
from typing import Any

# ── 颜色常量 ────────────────────────────────────────────
COLOR_INDEX = {
    "byblock": 0, "red": 1, "yellow": 2, "green": 3, "cyan": 4,
    "blue": 5, "magenta": 6, "white": 7, "bylayer": 256,
    "8": 8, "9": 9, "dark_red": 10, "dark_yellow": 11, "dark_green": 12,
    "dark_cyan": 13, "dark_blue": 14, "dark_magenta": 15,
}

# ── 线宽常量 ────────────────────────────────────────────
LINEWEIGHT = {
    "bylayer": -3, "byblock": -2, "default": -1,
    "0.00": 0, "0.05": 5, "0.09": 9, "0.13": 13, "0.15": 15,
    "0.18": 18, "0.20": 20, "0.25": 25, "0.30": 30, "0.35": 35,
    "0.40": 40, "0.50": 50, "0.53": 53, "0.60": 60, "0.70": 70,
    "0.80": 80, "0.90": 90, "1.00": 100, "1.06": 106,
    "1.20": 120, "1.40": 140, "1.58": 158, "2.00": 200, "2.11": 211,
}

# ══════════════════════════════════════════════════════════
# AutoCAD COM 控制器
# ══════════════════════════════════════════════════════════

class AcadController:
    """AutoCAD COM 连接管理 + 操作"""

    def __init__(self):
        self.acad = None
        self.doc = None
        self._connect()

    def _connect(self):
        import win32com.client
        try:
            self.acad = win32com.client.GetActiveObject("AutoCAD.Application")
            self.doc = self.acad.ActiveDocument
            if not self.doc:
                self.doc = self.acad.Documents.Add()
        except Exception:
            self.acad = None
            self.doc = None

    def _ensure(self):
        """确保连接有效，必要时重连"""
        if self.acad is None:
            self._connect()
            if self.acad is None:
                raise RuntimeError("无法连接到 AutoCAD，请确保 AutoCAD 已启动")
        try:
            _ = self.doc.Name
        except Exception:
            self._connect()
            if self.acad is None:
                raise RuntimeError("AutoCAD 连接已断开，请重新启动 AutoCAD")

    @property
    def connected(self):
        return self.acad is not None and self.doc is not None

    @staticmethod
    def _parse_color(color):
        if isinstance(color, str) and color.lower() in COLOR_INDEX:
            return COLOR_INDEX[color.lower()]
        if isinstance(color, str):
            try:
                return int(color)
            except ValueError:
                return 7
        if isinstance(color, (int, float)):
            return int(color)
        return 7

    @staticmethod
    def _parse_lineweight(lw):
        if isinstance(lw, (int, float)):
            return int(lw)
        key = str(lw).lower()
        if key in LINEWEIGHT:
            return LINEWEIGHT[key]
        try:
            return int(float(lw) * 100)
        except (ValueError, TypeError):
            return -1

    @staticmethod
    def _lw_to_str(val):
        if val == -3: return "ByLayer"
        if val == -2: return "ByBlock"
        if val == -1: return "Default"
        return f"{val / 100:.2f}mm"

    # ── 信息 ──
    def get_info(self):
        self._ensure()
        d = self.doc
        return {
            "version": self.acad.Version,
            "drawing": d.Name,
            "path": d.Path,
            "layer_count": d.Layers.Count,
            "text_style_count": d.TextStyles.Count,
            "dim_style_count": d.DimStyles.Count,
            "block_count": d.Blocks.Count,
            "current_layer": d.ActiveLayer.Name,
        }

    # ── 图层 ──
    def list_layers(self):
        self._ensure()
        layers = []
        for i in range(self.doc.Layers.Count):
            ly = self.doc.Layers.Item(i)
            layers.append({
                "name": ly.Name,
                "color_index": ly.color,
                "linetype": ly.Linetype,
                "lineweight": self._lw_to_str(ly.Lineweight),
                "on": ly.LayerOn,
                "freeze": ly.Freeze,
                "lock": ly.Lock,
                "description": ly.Description if hasattr(ly, 'Description') else "",
            })
        return layers

    def create_layer(self, name, color="7", linetype="Continuous",
                     lineweight="default", description="", on=True,
                     freeze=False, lock=False, plot=True):
        self._ensure()
        try:
            self.doc.Layers.Item(name)
            return {"status": "skipped", "reason": f"图层 '{name}' 已存在"}
        except Exception:
            pass
        ly = self.doc.Layers.Add(name)
        ly.color = self._parse_color(color)  # .color (not TrueColor — doesn't stick in 2025)
        if linetype and linetype != "Continuous":
            ly.Linetype = linetype
        ly.Lineweight = self._parse_lineweight(lineweight)
        ly.LayerOn = on
        ly.Freeze = freeze
        ly.Lock = lock
        if hasattr(ly, 'Description'):
            ly.Description = description or ""
        if hasattr(ly, 'Plottable'):
            ly.Plottable = plot
        return {"status": "created", "name": name}

    def set_layer(self, name, **kwargs):
        self._ensure()
        try:
            ly = self.doc.Layers.Item(name)
        except Exception:
            return {"status": "error", "reason": f"图层 '{name}' 不存在"}
        changes = {}
        for attr, val in kwargs.items():
            if val is None:
                continue
            try:
                if attr == "color":
                    ly.color = self._parse_color(val)
                elif attr == "linetype":
                    ly.Linetype = val
                elif attr == "lineweight":
                    ly.Lineweight = self._parse_lineweight(val)
                elif attr == "on":
                    ly.LayerOn = bool(val)
                elif attr == "freeze":
                    ly.Freeze = bool(val)
                elif attr == "lock":
                    ly.Lock = bool(val)
                elif attr == "description":
                    if hasattr(ly, 'Description'):
                        ly.Description = str(val)
                changes[attr] = val
            except Exception as e:
                changes[attr] = f"error: {e}"
        return {"status": "updated", "name": name, "changes": changes}

    def delete_layer(self, name):
        self._ensure()
        if name in ("0", "Defpoints"):
            return {"status": "error", "reason": f"不能删除系统图层 '{name}'"}
        try:
            self.doc.Layers.Item(name).Delete()
            return {"status": "deleted", "name": name}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    # ── 批量操作 ──
    def batch_create_layers(self, layers):
        """batch_create_layers(layers: list[dict]) — 批量创建图层"""
        self._ensure()
        results = []
        for ld in layers:
            name = ld.pop("name", "")
            if name:
                results.append(self.create_layer(name, **ld))
            else:
                results.append({"status": "error", "reason": "缺少 name"})
        return {"status": "done", "results": results}

    def batch_set_sysvars(self, variables):
        """batch_set_sysvars(variables: dict) — 批量设置系统变量"""
        self._ensure()
        results = {}
        for k, v in variables.items():
            results[k] = self.set_sysvar(k, v)
        return {"status": "done", "results": results}

    def set_current_layer(self, name):
        self._ensure()
        try:
            self.doc.ActiveLayer = self.doc.Layers.Item(name)
            return {"status": "current", "name": name}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    # ── 文字样式 ──
    def list_text_styles(self):
        self._ensure()
        styles = []
        for i in range(self.doc.TextStyles.Count):
            s = self.doc.TextStyles.Item(i)
            styles.append({
                "name": s.Name,
                "font_file": s.FontFile,
                "height": s.Height,
                "width": s.Width,
                "oblique_angle": s.ObliqueAngle,
            })
        return styles

    def create_text_style(self, name, font="arial.ttf", big_font="",
                          height=0.0, width=1.0):
        self._ensure()
        try:
            self.doc.TextStyles.Item(name)
            return {"status": "skipped", "reason": f"文字样式 '{name}' 已存在"}
        except Exception:
            pass
        style = self.doc.TextStyles.Add(name)
        style.SetFont(font, False, False, 134, 34)  # charset=134 → GB2312
        if big_font:
            style.BigFontFile = big_font
        if height > 0:
            style.Height = height
        style.Width = width
        return {"status": "created", "name": name, "font": font}

    def set_current_text_style(self, name):
        self._ensure()
        try:
            self.doc.ActiveTextStyle = self.doc.TextStyles.Item(name)
            return {"status": "current", "name": name}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    # ── 标注样式 ──
    def list_dim_styles(self):
        self._ensure()
        styles = []
        for i in range(self.doc.DimStyles.Count):
            s = self.doc.DimStyles.Item(i)
            styles.append({"name": s.Name})
        return styles

    def create_dim_style(self, name, copy_from="Standard"):
        self._ensure()
        try:
            self.doc.DimStyles.Item(name)
            return {"status": "skipped", "reason": f"标注样式 '{name}' 已存在"}
        except Exception:
            pass
        src = self.doc.DimStyles.Item(copy_from)
        ds = self.doc.DimStyles.Add(name)
        ds.CopyFrom(src)
        return {"status": "created", "name": name, "copied_from": copy_from}

    def set_dim_vars(self, style_name, **variables):
        """设置标注变量: DIMTXT, DIMASZ, DIMSCALE, DIMDEC, DIMEXE, DIMEXO, DIMDLI..."""
        self._ensure()
        self.doc.ActiveDimStyle = self.doc.DimStyles.Item(style_name)
        for var_name, val in variables.items():
            self.doc.SetVariable(var_name, val)
        return {"status": "updated", "style": style_name, "variables": variables}

    def set_current_dim_style(self, name):
        self._ensure()
        try:
            self.doc.ActiveDimStyle = self.doc.DimStyles.Item(name)
            return {"status": "current", "name": name}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    # ── 线型 ──
    def list_linetypes(self):
        self._ensure()
        lts = []
        for i in range(self.doc.Linetypes.Count):
            lt = self.doc.Linetypes.Item(i)
            lts.append({"name": lt.Name, "description": lt.Description})
        return lts

    def load_linetype(self, name, file="acad.lin"):
        self._ensure()
        try:
            self.doc.Linetypes.Load(name, file)
            return {"status": "loaded", "name": name}
        except Exception:
            for i in range(self.doc.Linetypes.Count):
                if self.doc.Linetypes.Item(i).Name == name:
                    return {"status": "already_loaded", "name": name}
            return {"status": "error", "reason": f"无法加载线型 '{name}'"}

    # ── 系统变量 ──
    def get_sysvar(self, name):
        self._ensure()
        try:
            return {"name": name, "value": self.doc.GetVariable(name)}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    def set_sysvar(self, name, value):
        self._ensure()
        try:
            self.doc.SetVariable(name, value)
            return {"status": "set", "name": name, "value": value}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    # ── 预设 ──
    def preset_gb_layers(self):
        self._ensure()
        # 确保 CENTER 线型已加载
        self.load_linetype("CENTER")
        layers = [
            {"name": "A-AXIS", "color": "1", "linetype": "CENTER", "description": "轴线"},
            {"name": "A-WALL", "color": "7", "description": "墙体"},
            {"name": "A-WALL-PART", "color": "8", "description": "隔墙"},
            {"name": "A-COLUMN", "color": "2", "description": "柱"},
            {"name": "A-DOOR", "color": "4", "description": "门"},
            {"name": "A-WINDOW", "color": "4", "description": "窗"},
            {"name": "A-STAIR", "color": "3", "description": "楼梯"},
            {"name": "A-DIM", "color": "3", "lineweight": "0.15", "description": "尺寸标注"},
            {"name": "A-TEXT", "color": "7", "lineweight": "0.15", "description": "文字"},
            {"name": "A-HATCH", "color": "8", "lineweight": "0.09", "description": "填充图案"},
            {"name": "A-FURN", "color": "8", "description": "家具"},
            {"name": "A-SANIT", "color": "4", "description": "卫生洁具"},
            {"name": "A-ELEC", "color": "6", "description": "电气"},
            {"name": "A-PIPE", "color": "5", "description": "管道"},
            {"name": "A-EQPM", "color": "2", "description": "设备"},
            {"name": "A-ELEV", "color": "1", "lineweight": "0.15", "description": "标高"},
            {"name": "A-SYMB", "color": "2", "lineweight": "0.15", "description": "符号"},
            {"name": "A-VPORT", "color": "8", "plot": False, "description": "视口"},
        ]
        results = []
        for ld in layers:
            name = ld.pop("name")
            results.append(self.create_layer(name, **ld))
        return {"status": "done", "created": len([r for r in results if r["status"] == "created"]), "skipped": len([r for r in results if r["status"] == "skipped"])}

    def preset_dim_style_arch(self, name="建筑标注-1:100", scale=100):
        self._ensure()
        result = self.create_dim_style(name)
        if result["status"] == "skipped":
            pass  # 已存在，跳过创建，继续设置变量
        variables = {
            "DIMSCALE": scale,
            "DIMTXT": 3.5 * scale / 100,
            "DIMASZ": 2.5 * scale / 100,
            "DIMEXE": 2.0 * scale / 100,
            "DIMEXO": 1.5 * scale / 100,
            "DIMDLI": 7.0 * scale / 100,
            "DIMLUNIT": 2,
            "DIMDEC": 0,
            "DIMDSEP": ord('.'),
            "DIMTIH": 0,
            "DIMTOH": 0,
            "DIMZIN": 8,
        }
        self.set_dim_vars(name, **variables)
        return {"status": "created", "name": name, "scale": scale, "variables": variables}


# ══════════════════════════════════════════════════════════
# MCP 协议实现 (stdio JSON-RPC)
# ══════════════════════════════════════════════════════════

TOOLS = [
    {
        "name": "autocad_info",
        "description": "获取当前 AutoCAD 图纸的基本信息：版本、文件名、图层/样式/图块数量、当前图层",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "layer_list",
        "description": "列出当前图纸中的所有图层及其属性（颜色、线型、线宽、开关/冻结/锁定状态）",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "layer_create",
        "description": "创建新图层。可指定颜色（索引号或颜色名如 red/blue/yellow）、线型（如 Continuous/CENTER/HIDDEN）、线宽（mm 值）、描述。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "图层名称"},
                "color": {"type": "string", "description": "颜色：索引号(1-256)或颜色名(red/yellow/green/cyan/blue/magenta/white)"},
                "linetype": {"type": "string", "description": "线型名称，默认 Continuous"},
                "lineweight": {"type": "string", "description": "线宽，如 0.25, 0.50, 0.70 (mm) 或 bylayer/byblock/default"},
                "description": {"type": "string", "description": "图层描述/说明"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "layer_set",
        "description": "修改现有图层的属性。可同时修改多个属性（颜色/线型/线宽/开关/冻结/锁定/描述）。只传需要修改的参数即可。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "图层名称"},
                "color": {"type": "string", "description": "颜色索引号或名称"},
                "linetype": {"type": "string", "description": "线型名称"},
                "lineweight": {"type": "string", "description": "线宽"},
                "on": {"type": "boolean", "description": "是否开启"},
                "freeze": {"type": "boolean", "description": "是否冻结"},
                "lock": {"type": "boolean", "description": "是否锁定"},
                "description": {"type": "string", "description": "图层描述"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "layer_delete",
        "description": "删除指定图层（不能删除 0 层和 Defpoints 层）",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "要删除的图层名称"}},
            "required": ["name"],
        },
    },
    {
        "name": "layer_set_current",
        "description": "将指定图层设为当前图层，之后绘制的对象将放在此图层上",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "要设为当前的图层名称"}},
            "required": ["name"],
        },
    },
    {
        "name": "layer_batch_create",
        "description": "批量创建多个图层。传入图层定义列表，一次性创建。适合一次性设置完整图层体系。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "layers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "color": {"type": "string"},
                            "linetype": {"type": "string"},
                            "lineweight": {"type": "string"},
                            "description": {"type": "string"},
                        },
                        "required": ["name"],
                    },
                },
            },
            "required": ["layers"],
        },
    },
    {
        "name": "text_style_list",
        "description": "列出当前图纸中所有文字样式（名称、字体、高度、宽度因子）",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "text_style_create",
        "description": "创建新文字样式。可指定字体文件、大字体（中文用）、高度、宽度因子。高度设为 0 表示使用时再指定。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "样式名称"},
                "font": {"type": "string", "description": "字体文件名，如 arial.ttf, simsun.ttf (宋体), simhei.ttf (黑体)"},
                "big_font": {"type": "string", "description": "大字体文件名，中文常用 gbcbig.shx"},
                "height": {"type": "number", "description": "字体高度，0=使用时指定"},
                "width": {"type": "number", "description": "宽度因子，默认 1.0"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "text_style_set_current",
        "description": "将指定文字样式设为当前样式",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "dim_style_list",
        "description": "列出当前图纸中所有标注样式",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "dim_style_create",
        "description": "创建标注样式（从现有样式复制后修改）。可指定复制源，默认从 Standard 复制。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "新标注样式名称"},
                "copy_from": {"type": "string", "description": "从哪个样式复制，默认 Standard"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "dim_style_set_vars",
        "description": "设置标注样式的变量。常用: DIMTXT(文字高度), DIMASZ(箭头大小), DIMSCALE(全局比例), DIMDEC(小数位数), DIMEXE(界线超出量), DIMEXO(起点偏移), DIMDLI(基线间距)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "style_name": {"type": "string", "description": "标注样式名称"},
                "DIMTXT": {"type": "number", "description": "文字高度"},
                "DIMASZ": {"type": "number", "description": "箭头大小"},
                "DIMSCALE": {"type": "number", "description": "全局比例因子"},
                "DIMDEC": {"type": "integer", "description": "小数位数 (0=整数, 2=两位小数)"},
                "DIMEXE": {"type": "number", "description": "尺寸界线超出量"},
                "DIMEXO": {"type": "number", "description": "尺寸界线起点偏移"},
                "DIMDLI": {"type": "number", "description": "基线标注间距"},
            },
            "required": ["style_name"],
        },
    },
    {
        "name": "dim_style_set_current",
        "description": "将指定标注样式设为当前样式",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "linetype_list",
        "description": "列出当前图纸已加载的线型",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "linetype_load",
        "description": "加载线型到当前图纸。常用线型: CENTER(点划线), HIDDEN(虚线), DASHED(虚线), PHANTOM(双点划线), DIVIDE, DOT",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "线型名称"},
                "file": {"type": "string", "description": "线型文件，默认 acad.lin (英制) 或 acadiso.lin (公制)"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "sysvar_get",
        "description": "读取 AutoCAD 系统变量。常用: OSMODE(对象捕捉), LTSCALE(线型比例), MIRRTEXT(镜像文字), DIMSCALE(标注比例)",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "系统变量名称"}},
            "required": ["name"],
        },
    },
    {
        "name": "sysvar_set",
        "description": "设置 AutoCAD 系统变量。支持整数、浮点数、字符串值。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "系统变量名称"},
                "value": {"description": "变量值 (整数/浮点/字符串)"},
            },
            "required": ["name", "value"],
        },
    },
    {
        "name": "sysvar_batch_set",
        "description": "批量设置多个系统变量。传入键值对列表，一次性修改多个变量。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "variables": {"type": "object", "description": "变量名→值的映射，如 {\"OSMODE\": 16383, \"LTSCALE\": 100, \"MIRRTEXT\": 0}"},
            },
            "required": ["variables"],
        },
    },
    {
        "name": "preset_gb_layers",
        "description": "一键部署 GB/T 建筑标准图层方案。创建 18 个标准图层：A-AXIS(轴线/CENTER线型)、A-WALL(墙体)、A-COLUMN(柱)、A-DOOR(门)、A-WINDOW(窗)、A-STAIR(楼梯)、A-DIM(标注)、A-TEXT(文字)、A-HATCH(填充)、A-FURN(家具)、A-SANIT(洁具)、A-ELEC(电气)、A-PIPE(管道)、A-EQPM(设备)、A-ELEV(标高)、A-SYMB(符号)、A-VPORT(视口/不打印)、A-WALL-PART(隔墙)。颜色和线宽按国标预设。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "preset_dim_style_arch",
        "description": "创建建筑标注样式，自动设置 DIMTXT/DIMASZ/DIMSCALE/DIMEXE 等变量。可指定比例（默认 1:100）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "标注样式名称，默认「建筑标注-1:100」"},
                "scale": {"type": "integer", "description": "绘图比例分母，如 50(1:50)、100(1:100)，默认 100"},
            },
        },
    },
]

# ────────────────────────────────────────────────────────
# MCP JSON-RPC 主循环
# ────────────────────────────────────────────────────────


class MCPServer:
    def __init__(self):
        self._ctrl = AcadController()
        self._handlers = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "ping": self._handle_ping,
        }

    def _handle_initialize(self, params, req_id):
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {
                "name": "AutoCAD MCP Server",
                "version": "1.0.0",
            },
        }

    def _handle_tools_list(self, params, req_id):
        return {"tools": TOOLS}

    def _handle_ping(self, params, req_id):
        return {}

    # 工具名 → 控制器方法名映射
    _TOOL_MAP = {
        "autocad_info": "get_info",
        "layer_list": "list_layers",
        "layer_create": "create_layer",
        "layer_set": "set_layer",
        "layer_delete": "delete_layer",
        "layer_set_current": "set_current_layer",
        "layer_batch_create": "batch_create_layers",
        "text_style_list": "list_text_styles",
        "text_style_create": "create_text_style",
        "text_style_set_current": "set_current_text_style",
        "dim_style_list": "list_dim_styles",
        "dim_style_create": "create_dim_style",
        "dim_style_set_vars": "set_dim_vars",
        "dim_style_set_current": "set_current_dim_style",
        "linetype_list": "list_linetypes",
        "linetype_load": "load_linetype",
        "sysvar_get": "get_sysvar",
        "sysvar_set": "set_sysvar",
        "sysvar_batch_set": "batch_set_sysvars",
        "preset_gb_layers": "preset_gb_layers",
        "preset_dim_style_arch": "preset_dim_style_arch",
    }

    def _handle_tools_call(self, params, req_id):
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        method_name = self._TOOL_MAP.get(tool_name)
        if method_name is None:
            return {"content": [{"type": "text", "text": json.dumps(
                {"status": "error", "reason": f"未知工具: {tool_name}"}, ensure_ascii=False)}], "isError": True}

        tool_func = getattr(self._ctrl, method_name, None)
        if tool_func is None:
            return {"content": [{"type": "text", "text": json.dumps(
                {"status": "error", "reason": f"控制器方法未找到: {method_name}"}, ensure_ascii=False)}], "isError": True}

        try:
            kwargs = {k: v for k, v in arguments.items() if v is not None}
            # dim_style_set_vars 用 style_name 参数
            if tool_name == "dim_style_set_vars":
                style_name = kwargs.pop("style_name", None)
                if not style_name:
                    return {"content": [{"type": "text", "text": json.dumps(
                        {"status": "error", "reason": "必须指定 style_name 参数"}, ensure_ascii=False)}], "isError": True}
                result = tool_func(style_name, **kwargs)
            elif tool_name == "layer_batch_create":
                layers = kwargs.pop("layers", [])
                result = self._ctrl.batch_create_layers(layers)
            elif tool_name == "sysvar_batch_set":
                variables = kwargs.pop("variables", {})
                results = []
                for k, v in variables.items():
                    results.append(self._ctrl.set_sysvar(k, v))
                result = {"status": "done", "results": results}
            elif kwargs:
                result = tool_func(**kwargs)
            else:
                result = tool_func()
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)}]}
        except Exception as e:
            return {"content": [{"type": "text", "text": json.dumps(
                {"status": "error", "reason": str(e), "tool": tool_name}, ensure_ascii=False)}], "isError": True}

    def run(self):
        for line in sys.stdin:
            try:
                msg = json.loads(line.strip())
            except json.JSONDecodeError:
                continue

            req_id = msg.get("id")
            method = msg.get("method", "")
            params = msg.get("params", {})

            # 通知消息（无 id），不需要回复
            if req_id is None:
                continue

            handler = self._handlers.get(method)
            if handler is None:
                resp = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}
            else:
                try:
                    result = handler(params, req_id)
                    resp = {"jsonrpc": "2.0", "id": req_id, "result": result}
                except Exception as e:
                    resp = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": str(e)}}

            self._write_response(resp)

    @staticmethod
    def _write_response(resp):
        line = json.dumps(resp, ensure_ascii=False, default=str)
        sys.stdout.write(line + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    MCPServer().run()
