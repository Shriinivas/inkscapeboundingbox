# Bounding Box Extension for Inkscape

This Inkscape extension allows users to create a bounding box around selected objects, individual elements within the selection, or the entire page. The extension provides various options to customize the bounding box, including positioning, size adjustments, addition of guides, and styling options for fill and stroke.

## Installation

1. **Download the Extension**: Download the files `bound_box.inx` and `bound_box.py` from this repository.
2. **Install the Extension**: Copy these files into your Inkscape extensions directory. You can find this in the 'User Extensions' option under the System section at Edit > Preferences in Inkscape.
3. **Restart Inkscape**: Close and reopen Inkscape to load the new extension.

## Features

This extension provides the following features:

- **Dynamic Bounding Box**: Create a bounding box that adjusts based on the selected objects, individual elements, or the entire page.
- **Positioning Options**: Choose where to add the bounding box relative to the selection or in a new layer.
- **Adjustable Size**: Increase or decrease the size of the bounding box.
- Retain Transform: For element and object bounding boxes, the bounding box can transform as per the selection
- **Guides**: Optionally add horizontal and/or vertical guides from the center of the bounding box.
- **Style Customization**: Specify fill and stroke colors for the bounding box.

## Usage

After installation, the extension can be accessed from the Inkscape menu under `Extensions > Render > Add Bounding Box`.

### Options

#### Config Tab:

- **Bounding Box Around**: Choose between Entire Selection, Elements (e.g. groups) within Selection, Individual Objects, or Entire Page.
- **Position**: Select where to add the bounding box:
  - `Below Selection`
  - `Above Selection`
  - `New Layer (Below)`
  - `New Layer (Above)`
- **Resize**: Adjust the size of the bounding box
- **Resize Type**: If `Absolute` box is extended by as many pixels as `Resize`, otherwise `Resize` is considered to be a percentage value
- **Retain Transform**: Bounding Box inherits the transform of the selection (applicable for element and object bounding boxes)
- **Horizontal Guide**: Add a horizontal guide across the middle of the bounding box.
- **Vertical Guide**: Add a vertical guide across the middle of the bounding box.

#### Fill Tab:

- **Add fill**: Enable or disable filling the bounding box with color.
- **Fill color**: Choose a color for the bounding box fill.

#### Stroke Tab:

- **Add stroke color**: Enable or disable the stroke outline for the bounding box.
- **Stroke color**: Choose a color for the bounding box stroke.

## License

This project is licensed under the GPL-3.0 License - see the [LICENSE](LICENSE) file for details.
