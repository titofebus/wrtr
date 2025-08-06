---
description: How to use wrtr to make blog posts with a main image, create images and more.
---
# 🖱️ How to Use wrtr with an IDE or LLM

Here's how you can use all the wrtr tools right inside your terminal for a smooth, fun, and productive workflow:

## 1. Write a Blog Post Automatically

- Open the built-in terminal.
- Run:
  ```sh
  pnpm exec tsx writeforme.ts "Your Blog Title" "A short description of your blog post." [keywords] [--skip-perplexity]
  ```
- This will write, extract metadata, and generate a hero image for your blog post!
- If you want the script to perform research using Perplexity, do not use the `--skip-perplexity` flag. If you use `--skip-perplexity`, it will skip the research step and generate a draft faster.

## 2. Generate Custom Images

- In the terminal, run:
  ```sh
  pnpm exec tsx generateimages.ts "A dreamy wedding venue at sunset" "A vintage camera on a table"
  ```
- Each argument is a separate image description. In this example it would create 2 images. Images are saved as `.webp` in your images directory.

## 3. Replace the Hero Image of the Latest Blog Post

- In the terminal, run:
  ```sh
  pnpm exec tsx replaceimage.ts "A new description for the hero image" [path/to/image.webp]
  ```
- If you do not provide an image path, this finds the latest blog post and replaces its hero image with a new AI-generated one. If you provide a path, it will use that image location instead.

---

## Project Configuration: `setup/wrtr.config.md`

All important settings for wrtr live in the `setup/wrtr.config.md` file! Here's what you can customize:

- **File Paths:**
  - `content_dir`: Where blog posts are saved
  - `image_dir`: Where hero images are saved
  - `general_image_dir`: Where custom/generated images are saved
  - `prompts_dir`: Where prompt templates are stored
- **Image Settings:**
  - `webp_quality`: Compression quality for `.webp` images (0-100, higher is better quality)
  - `webp_size`: Size for `.webp` images in `WIDTHxHEIGHT` format (e.g., `1536x1024`)
- **Blog Defaults:**
  - `default_frontmatter`: Default values for new blog posts (title, description, author, etc.)
- **Company Info:**
  - Used for prompt context and metadata (name, type, target audience, competitors, etc.)

**To change any of these, just edit the config file and rerun your scripts!**

---

## Troubleshoot

- **If you ever see a `dquote>` or `quote>` prompt:**
  - This means your shell thinks a quote is unclosed (for example, you started a string with a double or single quote but didn't close it).
  - This can happen if you copy-paste commands and miss a quote, or if your arguments contain special characters.
  - **How to fix:**
    - Press `Ctrl+C` to cancel the current command prompt.
    - Double-check your command for any missing or mismatched quotes.
    - Prefer using single quotes (`'`) around arguments, especially if your text contains spaces or special characters.
    - Example: `pnpm exec tsx writeforme.ts 'How to take great photos' 'A guide for beginners.'`
  - This is a shell/terminal thing, not a bug in the script! :)
