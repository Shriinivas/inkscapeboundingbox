#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inkscape extension to create a bounding box around selection or page.
Tested with Inkscape version 1.3.

Author: Shrinivas Kulkarni (khemadeva@gmail.com)

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License along
with this program; if not, write to the Free Software Foundation, Inc.,
51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""

import inkex
import tempfile, os
from inkex.command import write_svg
from inkex import (
    Effect,
    PathElement,
    command,
    errormsg,
    Color,
    Boolean,
    TextElement,
    Page,
    Layer,
    Rectangle,
)
from inkex.paths import Line, Move, Path


class BoundingBoxEffect(Effect):
    def __init__(self):
        super().__init__()
        arg = self.arg_parser.add_argument

        # Tab configurations
        arg("--tab", help="Select Options")
        arg("--colortab", help="Select Colors")

        # Options for bounding box
        arg(
            "--newlayer",
            type=Boolean,
            default=False,
            help="Create new layer with bounding box",
        )
        arg(
            "--horizgrid",
            type=int,
            default=0,
            help="Horizontal grid line count.",
        )
        arg(
            "--vertgrid",
            type=int,
            default=0,
            help="Vertical grid line count.",
        )
        arg(
            "--horizguide",
            type=Boolean,
            default=False,
            help="Create horizontal guide of bounding box",
        )
        arg(
            "--vertguide",
            type=Boolean,
            default=False,
            help="Create vertical guide of bounding box",
        )
        arg(
            "--bboxtype",
            default="selection",
            help="Draw box around selection or page",
        )
        arg(
            "--position",
            default="below_sel",
            help="Where to add the bounding box",
        )
        arg(
            "--grow_type",
            default="relative",
            help="How to interpret Grow / Shrink value",
        )
        arg(
            "--grow",
            type=int,
            default=0,
            help="Add/subtract value (or percentage) to/from box size",
        )
        arg(
            "--retain_transform",
            type=Boolean,
            default=False,
            help="Bounding Box inherits selection transform",
        )

        # Color options
        arg(
            "--addfill",
            type=Boolean,
            default=True,
            help="Add fill to bounding box",
        )
        arg(
            "--addstroke",
            type=Boolean,
            default=False,
            help="Add stroke to bounding box",
        )
        arg("--fillcolor", type=Color, help="Fill color for bounding box")
        arg("--strokecolor", type=Color, help="Stroke color for bounding box")
        arg("--strokewidth", type=float, help="Stroke width for bounding box")

    def get_sel_bbox_info_external(self, elements, retain_transform):
        element_ids = [elem.get_id() for elem in elements]
        transforms = []

        if retain_transform:
            for elem in elements:
                transforms.append(elem.transform)
                elem.transform = -elem.getparent().composed_transform()

        tmp_path = write_svg(
            self.document, os.path.join(tempfile.gettempdir(), "__bbox_ext.svg")
        )

        try:
            cmd = ["--query-id=" + ",".join(element_ids)]
            queries = ["--query-x", "--query-y", "--query-width", "--query-height"]
            cmd.extend(queries)

            result = command.inkscape(tmp_path, *cmd).strip()  # type: ignore
            lines = result.split("\n")
            bboxVals = [line.split(",") for line in lines]
            bbox_info = []

            for i, (x, y, w, h) in enumerate(zip(*bboxVals)):
                x, y, w, h = map(self.svg.unittouu, map(float, (x, y, w, h)))
                bbox_info.append([elements[i], [x, y, x + w, y + h]])
            return bbox_info
        finally:
            try:
                for elem, transform in zip(elements, transforms):
                    elem.transform = transform
                os.remove(tmp_path)

            except Exception as e:
                errormsg(f"Failed to delete temporary file: {tmp_path}\nError: {e}")

    def get_sel_bbox_info(self, elements, retain_transform):
        if not elements:
            return None
        if any(isinstance(ec, TextElement) for e in elements for ec in e.descendants()):
            bbox_info = self.get_sel_bbox_info_external(elements, retain_transform)
        else:
            if retain_transform:
                bbs = [[e, e.bounding_box(-e.transform)] for e in elements]
            else:
                bbs = [
                    [e, e.bounding_box(e.getparent().composed_transform())]
                    for e in elements
                ]
            bbox_info = [
                [bb[0], [bb[1].left, bb[1].top, bb[1].right, bb[1].bottom]]
                for bb in bbs
            ]
        return bbox_info

    def get_combined_bbox(self, elements, retain_transform):
        bbox_info = self.get_sel_bbox_info(elements, retain_transform)
        if not bbox_info:
            return None
        min_x, min_y = (min(b[1][i] for b in bbox_info) for i in range(2))
        max_x, max_y = (max(b[1][i] for b in bbox_info) for i in range(2, 4))
        return min_x, min_y, max_x, max_y

    def find_page_containing_point(self, pages, points):
        for page in pages:
            bbox = page.bounding_box
            for point_x, point_y in points:
                if (
                    bbox.left <= point_x <= bbox.right
                    and bbox.top <= point_y <= bbox.bottom
                ):
                    return page
        return None

    def get_page_bbox(self, elements):
        pages = self.svg.descendants().get(Page)
        page = None

        if len(pages) == 0:
            pass  # Intentionally do nothing to allow fall-through to document-size calculation
        elif len(pages) == 1 or not elements:
            page = pages[0]
        else:
            points = [self.get_combined_bbox([e])[:2] for e in elements]  # type: ignore
            page = self.find_page_containing_point(pages, points)

        if page is not None:
            box = page.bounding_box
            x, y, width, height = box.left, box.top, box.width, box.height
        else:
            x = y = 0
            width, height = (
                self.svg.unittouu(dim)
                for dim in (self.svg.viewport_width, self.svg.viewport_height)
            )
        return x, y, x + width, y + height

    def add_line(self, x1, y1, x2, y2, strokecolor, strokewidth, transform, label):
        path_elem = PathElement()
        path_elem.path = Path([Move(x1, y1), Line(x2, y2)])
        path_elem.style.set_color(strokecolor, "stroke")
        path_elem.style["stroke-width"] = str(f"{strokewidth:.2f}")
        path_elem.transform = transform
        path_elem.label = label
        return path_elem

    def add_rect(
        self, x, y, width, height, fillcolor, strokecolor, strokewidth, transform, label
    ):
        rect = Rectangle()
        rect.style.set_color(fillcolor if fillcolor else "None", "fill")
        rect.style.set_color(strokecolor if strokecolor else "None", "stroke")
        rect.style["stroke-width"] = str(f"{strokewidth:.2f}")  # even if no strokecolor
        rect.set("width", str(f"{width}px"))
        rect.set("height", str(f"{height}px"))
        rect.set("x", str(f"{x}px"))
        rect.set("y", str(f"{y}px"))
        rect.transform = transform
        rect.label = label
        return rect

    def get_bbox_info(self, elements, bboxtype, position, retain_transform):
        # Determine bounding box based on user selection
        if bboxtype == "selection":
            elem = elements[-1] if position == "above_sel" else elements[0]
            bbox_info = [[elem, self.get_combined_bbox(elements, retain_transform)]]

        elif bboxtype == "elements":
            bbox_info = self.get_sel_bbox_info(elements, retain_transform)
        elif bboxtype == "objects":
            # Get all subclasses of ShapeElement (Can have some unforeseen effects)
            # shape_classes = [
            #     cls
            #     for cls in ShapeElement.__subclasses__()
            #     if cls is not inkex.elements._groups.GroupBase
            #     and not issubclass(cls, inkex.elements._groups.GroupBase)
            # ]
            shape_classes = {
                inkex.PathElement,
                inkex.TextElement,
                inkex.Rectangle,
                inkex.Ellipse,
                inkex.Circle,
                inkex.Polygon,
            }
            bbox_info = self.get_sel_bbox_info(
                elements.get(*shape_classes), retain_transform
            )
        else:
            bbox_info = [[None, self.get_page_bbox(elements)]]
        return bbox_info

    def get_parent_layer(self, elem):
        parent = elem.getparent()
        if parent is None or parent.get("inkscape:groupmode") == "layer":
            return parent
        return self.get_parent_layer(parent)

    def get_bbox_layer(self, position, ref_elem):
        if position in {"below_layer", "above_layer"}:
            layer = Layer.new("Bounding Box Layer")
            pos_ref = (
                self.get_parent_layer(ref_elem)
                if ref_elem is not None
                else self.svg.get_current_layer()
            )
            if pos_ref is None or pos_ref == self.svg:
                pos_ref = ref_elem
            if position == "below_layer":
                pos_ref.addprevious(layer)
            else:
                pos_ref.addnext(layer)
        else:
            layer = self.svg.get_current_layer()

        return layer

    def add_rect_and_lines(
        self,
        layer,
        ref_elem,
        position,
        x1,
        y1,
        width,
        height,
        fillcolor,
        addstroke,
        strokecolor,
        strokewidth,
        rect_transform,
        horizgrid,
        vertgrid,
    ):
        new_elems = []

        # Draw the bounding box
        rect = self.add_rect(
            x1,
            y1,
            width,
            height,
            fillcolor,
            strokecolor if addstroke else None,
            strokewidth,
            rect_transform,
            "Bounding Box",
        )
        new_elems.append(rect)
        strokewidth = strokewidth or 1

        vertdist = height / max((horizgrid + 1), 1)
        for i in range(horizgrid):
            vertoffset = (i + 1) * vertdist
            new_elems.append(
                self.add_line(
                    x1,
                    y1 + vertoffset,
                    x1 + width,
                    y1 + vertoffset,
                    strokecolor,
                    strokewidth,
                    rect_transform,
                    "gridline",
                )
            )
        horizdist = width / max((vertgrid + 1), 1)
        for i in range(vertgrid):
            horizoffset = (i + 1) * horizdist
            new_elems.append(
                self.add_line(
                    x1 + horizoffset,
                    y1,
                    x1 + horizoffset,
                    y1 + height,
                    strokecolor,
                    strokewidth,
                    rect_transform,
                    "gridline",
                )
            )

        if position == "above_sel" and ref_elem is not None:
            for new_elem in new_elems:
                ref_elem.addnext(new_elem)
        elif position == "below_sel" and ref_elem is not None:
            for new_elem in new_elems:
                ref_elem.addprevious(new_elem)
        else:
            for new_elem in new_elems:
                layer.add(new_elem)

        return rect, new_elems

    def add_bboxes(
        self,
        bbox_info,
        layer,
        position,
        grow_type,
        grow,
        fillcolor,
        addstroke,
        strokecolor,
        strokewidth,
        retain_transform,
        horizgrid,
        vertgrid,
    ):
        guide_x1 = guide_y1 = float("inf")
        guide_x2 = guide_y2 = float("-inf")

        for elem, (x1, y1, x2, y2) in bbox_info:
            parent = (
                elem.getparent()
                if elem is not None and position in {"above_sel", "below_sel"}
                else layer
            )

            rect_transform = (
                (
                    -parent.composed_transform()
                    @ elem.getparent().composed_transform()
                    @ elem.transform
                )
                if retain_transform
                else -parent.composed_transform()
            )

            tr = rect_transform @ parent.composed_transform()
            a, b, c, d = tr.a, tr.b, tr.c, tr.d
            strokewidth *= abs(a * d - b * c) ** -0.5

            scale_x = (a * a + c * c) ** 0.5
            scale_y = (b * b + d * d) ** 0.5

            width = x2 - x1
            height = y2 - y1

            width_increase = (
                (grow / scale_x) if grow_type == "absolute" else (width * grow) / 100
            )
            height_increase = (
                (grow / scale_y) if grow_type == "absolute" else (height * grow) / 100
            )

            x1 -= width_increase / 2
            y1 -= height_increase / 2
            width += width_increase
            height += height_increase

            rect, _ = self.add_rect_and_lines(
                layer,
                elem,
                position,
                x1,
                y1,
                width,
                height,
                fillcolor,
                addstroke,
                strokecolor,
                strokewidth,
                rect_transform,
                horizgrid,
                vertgrid,
            )
            abs_bb = rect.bounding_box(parent.composed_transform())
            if abs_bb:
                guide_x1 = min(guide_x1, abs_bb.left)
                guide_y1 = min(guide_y1, abs_bb.top)
                guide_x2 = max(guide_x2, abs_bb.right)
                guide_y2 = max(guide_y2, abs_bb.bottom)
        return guide_x1, guide_y1, guide_x2, guide_y2

    def effect(self):
        position = self.options.position
        horizguide = self.options.horizguide
        vertguide = self.options.vertguide
        addfill = self.options.addfill
        addstroke = self.options.addstroke
        fillcolor = self.options.fillcolor if addfill else None
        strokecolor = self.options.strokecolor
        strokewidth = self.options.strokewidth
        bboxtype = self.options.bboxtype
        grow_type = self.options.grow_type
        grow = self.options.grow
        horizgrid = self.options.horizgrid
        vertgrid = self.options.vertgrid
        retain_transform = self.options.retain_transform and bboxtype not in {
            "page",
            "selection",
        }

        elements = self.svg.selected.rendering_order()
        bbox_info = self.get_bbox_info(elements, bboxtype, position, retain_transform)

        if not bbox_info:
            errormsg("No selection for bounding box.")
            return

        layer = self.get_bbox_layer(position, elements[0] if elements else None)

        guide_x1, guide_y1, guide_x2, guide_y2 = self.add_bboxes(
            bbox_info,
            layer,
            position,
            grow_type,
            grow,
            fillcolor,
            addstroke,
            strokecolor,
            strokewidth,
            retain_transform,
            horizgrid,
            vertgrid,
        )
        # Add Guides
        if vertguide:
            xmid = (guide_x1 + guide_x2) / 2
            self.svg.namedview.add_guide(xmid, False)
        if horizguide:
            ymid = (guide_y1 + guide_y2) / 2
            self.svg.namedview.add_guide(ymid, True)


BoundingBoxEffect().run()
