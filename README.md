# Photo Deleter - Image Sorter

A simple desktop application built with Python and PyQt5 for quickly sorting images from a folder into "kept" and "deleted" subdirectories. It provides a match-like interface for quickly making decisions on a large number of photos.

## How it Works

The application displays images one by one from a selected directory. For each image, you have two choices:

- **Keep**: Moves the image to a `kept` subfolder inside the source directory.
- **Delete**: Moves the image to a `deleted` subfolder inside the source directory.

The `kept` and `deleted` folders are created automatically if they don't exist. The application handles file name collisions by appending a number to the filename (e.g., `image_1.jpg`).

## Features

- **Directory Chooser**: Select any folder on your computer to start sorting images.
- **Image Preview**: Displays a scalable preview of the current image.
- **Simple Controls**: Use buttons or keyboard shortcuts to sort.
- **Supported formats**: `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.bmp`.

## Installation

This project requires Python 3 and PyQt5.

1.  **Clone the repository (or download the source code):**
    ```bash
    git clone <repository-url>
    cd photo-deleter
    ```

2.  **Create and activate a virtual environment (recommended):**
    - On macOS/Linux:
      ```bash
      python3 -m venv .venv
      source .venv/bin/activate
      ```
    - On Windows:
      ```bash
      python -m venv .venv
      .venv\Scripts\activate
      ```

3.  **Install the required packages:**
    ```bash
    pip install -r requirements.txt
    ```

## How to Run

Once the dependencies are installed, run the application from your terminal:

```bash
python app.py
```

The application window will open.

## Usage

1.  **Choose a Directory**: Click the "Choose Directory" button and navigate to the folder containing the images you want to sort.
2.  **Sort Images**:
    - Click the green **Keep** button or press the **Right Arrow** key to move the current image to the `kept` folder.
    - Click the red **Delete** button or press the **Left Arrow** key to move the current image to the `deleted` folder.
    - Press the **Spacebar** to skip the current image and move to the next one.
3.  **Completion**: When all images in the directory have been sorted, a "No more images" message will be displayed.

You can then find your sorted images in the `kept` and `deleted` subfolders within the directory you originally selected.
