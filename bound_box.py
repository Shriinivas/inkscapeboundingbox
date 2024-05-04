#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inkscape extension to create a bounding box around selection or page.
Tested with Inkscape version 1.3.

Copyright (C) 2024  Shrinivas Kulkarni (khemadeva@gmail.com)

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
from lxml import etree
import tempfile, os
from inkex.transforms import Transform


class BoundingBoxEffect(inkex.Effect):
    def __init__(self):
        super().__init__()
        arg = self.arg_parser.add_argument

        # Tab configurations
        arg("--tab", help="Select Options")
        arg("--colortab", help="Select Colors")

        # Options for bounding box
        arg(
            "--newlayer",
            type=inkex.Boolean,
            default=False,
            help="Create new layer with bounding box",
        )
        arg(
            "--horizbisector",
            type=inkex.Boolean,
            default=False,
            help="Create horizontal bisector of bounding box",
        )
        arg(
            "--vertbisector",
            type=inkex.Boolean,
            default=False,
            help="Create vertical bisector of bounding box",
        )
        arg(
            "--bboxtype",
            choices=["selection", "page"],
            default="selection",
            help="Draw box around selection or page",
        )
        arg(
            "--grow",
            type=float,
            default=0,
            help="Grow or shrink the bounding box by percentage",
        )

        # Color options
        arg(
            "--addfill",
            type=inkex.Boolean,
            default=True,
            help="Add fill to bounding box",
        )
        arg(
            "--addstroke",
            type=inkex.Boolean,
            default=False,
            help="Add stroke to bounding box",
        )
        arg("--fillcolor", type=inkex.Color, help="Fill color for bounding box")
        arg("--strokecolor", type=inkex.Color, help="Stroke color for bounding box")

    def get_transform(self, elem, transform):
        """
        Recursively accumulate the transformation matrices from the given element up to the root.

        Args:
        elem : lxml.etree.Element
            The starting element from which to accumulate transformations.
        transform : inkex.Transform
            The current transformation matrix.

        Returns:
        inkex.Transform
            The accumulated transformation matrix up to the root.
        """
        current_transform = Transform(elem.get("transform")) @ transform
        parent = elem.getparent()
        if parent is None:
            return current_transform
        else:
            return self.get_transform(parent, current_transform)

    def get_combined_bbox_internal(self, items):
        """
        Calculate the combined bounding box for a collection of items.
        Works for elements other than text, as `bounding_box` does not handle text elements.

        Args:
        items : list of tuples
            A list of (id, element) tuples where each element is an SVG element.

        Returns:
        tuple
            The coordinates and dimensions of the bounding box (minx, miny, width, height).
        """
        minx, miny, maxx, maxy = (
            float("inf"),
            float("inf"),
            float("-inf"),
            float("-inf"),
        )

        for _, element in items:
            box = element.bounding_box(
                self.get_transform(element.getparent(), Transform())
            )
            minx = min(minx, box.left)
            miny = min(miny, box.top)
            maxx = max(maxx, box.right)
            maxy = max(maxy, box.bottom)

        return minx, miny, (maxx - minx), (maxy - miny)

    def get_combined_bbox_external(self):
        """
        Calculate the combined bounding box for selected elements using an external Inkscape process.
        This method is specifically used for elements like text, where internal methods cannot compute bounding boxes.

        This function reads the current SVG document, writes it to a temporary file, and invokes a headless
        Inkscape process to compute bounding boxes for selected elements. It parses the output to derive
        the minimum and maximum extents and returns these as converted units.

        Returns:
        tuple of floats
            A tuple containing the converted units of the minimum x, minimum y, width, and height of the
            bounding box encompassing all selected elements.
        """
        element_ids = [elem.get_id() for elem in self.svg.selection]

        svg_content = etree.tostring(self.document, encoding="unicode")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".svg") as tmp:
            tmp_path = tmp.name
            tmp.write(svg_content.encode("utf-8"))
            tmp.flush()

        try:
            command = ["--query-id=" + ",".join(element_ids)]
            queries = ["--query-x", "--query-y", "--query-width", "--query-height"]
            command.extend(queries)

            result = inkex.command.inkscape(tmp_path, *command).strip()
            lines = result.split("\n")
            bboxVals = [line.split(",") for line in lines]
            bboxVals = list(zip(*bboxVals))

            min_x = min_y = float("inf")
            max_x = max_y = -float("inf")

            for x, y, w, h in bboxVals:
                x, y, w, h = map(float, (x, y, w, h))
                x2, y2 = x + w, y + h
                min_x, max_x = min(min_x, x), max(max_x, x2)
                min_y, max_y = min(min_y, y), max(max_y, y2)

            return (
                self.svg.unittouu(min_x),
                self.svg.unittouu(min_y),
                self.svg.unittouu(max_x - min_x),
                self.svg.unittouu(max_y - min_y),
            )
        finally:
            try:
                os.remove(tmp_path)
            except Exception as e:
                inkex.errormsg(
                    f"Failed to delete temporary file: {tmp_path}\nError: {e}"
                )

    def get_selection_bbox(self):
        """
        Calculate the bounding box for the currently selected elements in the SVG document.

        This method checks if any of the selected elements are text elements and uses an external
        method to calculate the bounding box, as the internal method does not support text elements.
        If no text elements are found, it uses the internal method for other types of elements.

        Returns:
        tuple of floats or None
            A tuple containing the x, y coordinates, width, and height of the bounding box
            encompassing all selected elements, or None if no elements are selected.
        """
        selected = self.svg.selected
        if not selected:
            return None
        if any(item[1].tag == inkex.addNS("text", "svg") for item in selected.items()):
            x, y, width, height = self.get_combined_bbox_external()
        else:
            items = selected.items()
            x, y, width, height = self.get_combined_bbox_internal(items)
        return x, y, width, height

    def find_page_containing_point(self, pages, points):
        """
        Return the first page that contains any of the given points.

        This method iterates over each page and checks if any point from a list of points falls within the page's bounding box.
        It's particularly useful in multi-page documents to determine the most relevant page for a set of graphical elements.

        Args:
        pages : list
            A list of page elements to check against.
        points : list of tuples
            A list of (x, y) tuples representing points to be checked.

        Returns:
        lxml.etree.Element or None
            The first page element containing any point, or None if no such page exists.
        """
        for page in pages:
            bbox = page.bounding_box
            for point_x, point_y in points:
                if (
                    bbox.left <= point_x <= bbox.right
                    and bbox.top <= point_y <= bbox.bottom
                ):
                    return page
        return None

    def get_page_bbox(self):
        """
        Calculate the bounding box for a page in the SVG document based on the current selection.

        If there are multiple pages and a selection is made, the method chooses any page
        containing the top left corner of any of the selected element's bounding box. If there's only one page
        or no selection, it defaults to the first page. If no pages are defined, it uses the entire document size.

        Returns:
        tuple of floats
            A tuple containing the x, y coordinates, width, and height of the bounding box of the selected page
            or the entire document if no pages are defined.
        """

        svg = self.document.getroot()
        selected = self.svg.selected
        pages = self.document.xpath("//inkscape:page", namespaces=inkex.NSS)
        page = None

        if len(pages) == 0:
            pass  # Intentionally do nothing to allow fall-through to document-size calculation
        elif len(pages) == 1 or not selected:
            page = pages[0]
        else:
            points = [
                self.get_combined_bbox_internal([item])[:2] for item in selected.items()
            ]
            page = self.find_page_containing_point(pages, points)

        if page is not None:
            box = page.bounding_box
            x, y, width, height = box.left, box.top, box.width, box.height
        else:
            x = y = 0
            width = self.svg.unittouu(svg.get("width"))
            height = self.svg.unittouu(svg.get("height"))
        return x, y, width, height

    def add_layer(self, label, lock=False):
        """
        Create a new layer in the SVG document root and optionally lock it.

        Args:
        label : str
            The label for the new layer.
        lock : bool, optional
            If True, the layer is made insensitive to interactions (locked).

        Returns:
        lxml.etree.Element
            The newly created SVG group element configured as an Inkscape layer.
        """
        svg = self.document.getroot()
        layer = etree.SubElement(svg, "g")
        layer.set(inkex.addNS("label", "inkscape"), label)
        layer.set(inkex.addNS("groupmode", "inkscape"), "layer")
        svg.insert(0, layer)
        if lock:
            layer.set("sodipodi:insensitive", "true")
        return layer

    def add_path(self, layer, d, label, strokecolor=None):
        """
        Add a path element to the specified layer with the provided path data and optional stroke color.

        Args:
        layer : lxml.etree.Element
            The layer to which the path will be added.
        d : str
            The path data string (contents of the 'd' attribute).
        label : str
            The label for the path element.
        strokecolor : str, optional
            The color of the stroke. If None, no stroke is applied.

        Returns:
        lxml.etree.Element
            The newly created path element.
        """
        path = etree.SubElement(layer, inkex.addNS("path", "svg"))
        path.set("d", d)
        layer.insert(0, path)
        path.style.set_color(strokecolor if strokecolor else "None", "stroke")
        path.set(inkex.addNS("label", "inkscape"), label)
        return path

    def add_rect(self, layer, x, y, width, height, label, fillcolor, strokecolor):
        """
        Add a rectangle element to the specified layer with given position, dimensions, and styles.

        Args:
        layer : lxml.etree.Element
            The layer to which the rectangle will be added.
        x, y : float
            The x and y coordinates of the rectangle.
        width, height : float
            The width and height of the rectangle.
        label : str
            The label for the rectangle element.
        fillcolor : str
            The color of the fill. If None, no fill is applied.
        strokecolor : str
            The color of the stroke. If None, no stroke is applied.

        Returns:
        lxml.etree.Element
            The newly created rectangle element.
        """
        rect = etree.SubElement(layer, inkex.addNS("rect", "svg"))
        layer.insert(0, rect)
        rect.style.set_color(fillcolor if fillcolor else "None", "fill")
        rect.style.set_color(strokecolor if strokecolor else "None", "stroke")
        rect.set("width", str(f"{width}px"))
        rect.set("height", str(f"{height}px"))
        rect.set("x", str(f"{x}px"))
        rect.set("y", str(f"{y}px"))
        rect.set(inkex.addNS("label", "inkscape"), label)
        return rect

    def effect(self):
        """
        Main method executed by the Inkscape extension to add a bounding box around the selected objects or page.
        This method also supports adding bisectors and growing/shrinking the bounding box based on user input.
        """
        # Fetch options
        newlayer = self.options.newlayer
        horizbisector = self.options.horizbisector
        vertbisector = self.options.vertbisector
        addfill = self.options.addfill
        addstroke = self.options.addstroke
        fillcolor = self.options.fillcolor
        strokecolor = self.options.strokecolor
        bboxtype = self.options.bboxtype
        grow = self.options.grow

        # Get document root
        svg = self.document.getroot()

        # Determine bounding box based on user selection
        if bboxtype == "selection":
            result = self.get_selection_bbox()
            if not result:
                inkex.errormsg("No selection found.")
                return
            x, y, width, height = result
        else:
            x, y, width, height = self.get_page_bbox()

        # Layer handling
        if newlayer:
            layer = self.add_layer("Bounding Box Layer")
        else:
            # Consider layer transform and apply reverse to ensure the correct BB position
            layer = svg.get_current_layer()
            transform_attr = layer.get("transform")
            if transform_attr:
                transform = Transform(transform_attr)
                x_end, y_end = (-transform).apply_to_point((x + width, y + height))
                x, y = (-transform).apply_to_point((x, y))
                width, height = x_end - x, y_end - y

        # Adjust bounding box size based on growth
        width_increase = (width * grow) / 100
        height_increase = (height * grow) / 100
        x -= width_increase / 2
        y -= height_increase / 2
        width += width_increase
        height += height_increase

        # Draw bisectors if needed
        bisect_color = strokecolor if addstroke else "#0000FF"
        if vertbisector:
            xmid = x + (width / 2)
            d = f"M {xmid},{y} V {height + y}"
            self.add_path(layer, d, "Vertical Bisector", bisect_color)
        if horizbisector:
            ymid = y + (height / 2)
            d = f"M {x},{ymid} H {width + x}"
            self.add_path(layer, d, "Horizontal Bisector", bisect_color)

        # Draw the bounding box
        self.add_rect(
            layer,
            x,
            y,
            width,
            height,
            "Bounding Box",
            fillcolor if addfill else None,
            strokecolor if addstroke else None,
        )


BoundingBoxEffect().run()
