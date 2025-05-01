# ✍️ Wrtr Blog Automation Suite

Welcome to the **Wrtr** tools! This suite automates blog post creation using OpenAI, research using Perplexity, AI-powered image generation using OpenAI, and hero image replacement for any mistakes. All written in Typescript. Everything is modular, robust, and easy to use. 🚀

---

## 📦 What's Inside?

- **writeforme.ts** – Fully automates blog post creation (research, writing, metadata, hero image)
- **generateimages.ts** – Generate custom AI images for any description
- **replaceimage.ts** – Instantly replace the hero image of your latest blog post
- **setup/wrtr.config.md** – Centralized config for all company info, file and directory paths, and blog frontmatter (edit this to update settings!)
- **setup/main-prompt.txt** – The main prompt template for AI calls (**edit this to change prompt style or instructions**)
- **setup/system-prompts/** – All other prompt templates (advanced, rarely edited) and the config loader

---

## 🛠️ Setup & Prerequisites

1. **Install dependencies:**
   - From the project root: `pnpm install` (installs everything for the monorepo)
   - Or, from inside `wrtr/`: `pnpm install` (installs just the wrtr tool dependencies)

2. **Environment variables:**
   Create a `.env` file in the project root (or `wrtr/`):
   ```env
   OPENAI_API_KEY=sk-...
   PERPLEXITY_API_KEY=pxy-...
   ```
   Both are required for full automation. (You can skip Perplexity with a flag.)

3. **Check & update config:**
   - All project, company, and blog settings are now in [`setup/wrtr.config.md`](./setup/wrtr.config.md) as a friendly markdown file with YAML frontmatter.
   - **To update company info, blog paths, or frontmatter defaults, just edit this file!**
   - No need to touch any TypeScript files for config anymore.

---

## ✨ Usage

You can run scripts from the project root (with `pnpm exec tsx ...`) or from inside the `wrtr/` folder using the provided scripts:

### 1. 📝 Write a Blog Post Automatically

```sh
pnpm exec tsx writeforme.ts "Your Blog Title" "A short description of your blog post." [keywords] [--skip-perplexity]
```
- **Arguments:**
  1. Blog Title (optional)
  2. Blog Description (optional)
  3. Keywords (optional)
  4. `--skip-perplexity` (optional): Skip research step for faster draft

- **What it does:**
  - Researches your topic (Perplexity, unless skipped)
  - Generates a markdown blog post (OpenAI)
  - Extracts metadata (title, description, image prompt)
  - Saves `.mdx` in `blog/` or where ever it's set up.
  - Generates a hero image and saves as `.webp` in `blog-images/` or where ever it's set up.

### 2. 🖼️ Generate Custom Images

```sh
pnpm exec tsx generateimages.ts "A dreamy wedding venue at sunset" "A vintage camera on a table" "A bouquet of wildflowers"
```
- Each argument is a separate image description.
- Images are saved as `.webp` in `images/` or where ever it's set up.
- Prompts are styled using `setup/wrtr.config.md`.

### 3. 🔄 Replace the Hero Image of the Latest Blog Post

```sh
pnpm exec tsx replaceimage.ts "A new description for the hero image" [path/to/image.webp]
```
- Finds the most recently modified `.mdx` in `blog/` (unless you specify an image path)
- Generates a new hero image using your description
- Overwrites the old image in `blog-images/` (or at the path you specify)

---

## 🧩 How It Works

1. **Research:** Calls Perplexity API to get a research summary and citations for your topic (unless skipped).
2. **Article Generation:** Uses OpenAI to generate a long-form markdown article based on the research.
3. **Metadata Extraction:** Extracts title, description, and image prompt from the article.
4. **MDX File Creation:** Saves the article as an `.mdx` file in `blog/` or where ever it's set up with proper frontmatter.
5. **Image Generation:** Generates a webp illustration and saves it in `blog-images/` or where ever it's set up.

---

## 🛠️ Configuration

- **All config is in [`setup/wrtr.config.md`](./setup/wrtr.config.md)** as YAML frontmatter in a markdown file.
- This includes company info, blog/image directory paths, and default blog frontmatter fields.
- **To update anything, just edit this file!**
- The loader at [`setup/system-prompts/config-loader.ts`](./setup/system-prompts/config-loader.ts) reads this config and makes it available to all scripts.

---

## 🎨 Customization & Advanced

- **Prompt templates:** Edit [`setup/main-prompt.txt`](./setup/main-prompt.txt) for the main prompt style or instructions for the AI.
- **Image style:** Edit [`setup/wrtr.config.md`](./setup/wrtr.config.md) to change the look, mood, or art direction of your generated images.
- **Advanced prompt templates** (for metadata, research, images) live in [`setup/system-prompts/`](./setup/system-prompts/) and rarely need editing.

---

## 💡 Tips & Troubleshooting

- Use clear, vivid descriptions for best image results (e.g., "A dreamy clock melting into a soft sunrise, symbolizing time and new beginnings").
- If you see an error about missing frontmatter or image, check your latest blog post for the correct fields.
- The script only updates the image—it does not change the blog content or frontmatter.
- Make sure your API keys are valid and have enough quota.
- If you see errors about missing dependencies, run `pnpm install` again.
- For debugging, check the console output for detailed logs and error messages.
- If you ever see a `dquote>` or `quote>` prompt, it means your shell thinks a quote is unclosed. Using single quotes for arguments helps avoid this issue.
- **If you ever see a `dquote>` or `quote>` prompt:**
  - This means your shell thinks a quote is unclosed (for example, you started a string with a double or single quote but didn't close it).
  - This can happen if you copy-paste commands and miss a quote, or if your arguments contain special characters.
  - **How to fix:**
    - Press `Ctrl+C` to cancel the current command prompt.
    - Double-check your command for any missing or mismatched quotes.
    - Prefer using single quotes (`'`) around arguments, especially if your text contains spaces or special characters.
    - Example: `pnpm exec tsx writeforme.ts 'How to take great photos' 'A guide for beginners.'`
  - This is a shell/terminal thing, not a bug in the script! :)
- Use `--skip-perplexity` for a faster run or if you don't need research/citations.

---

## 📝 Notes

- This script is designed for use with an MDX blog setup.
- All code follows clean code and modularity best practices.
- If you want to customize prompts or output, check the `wrtr/setup/system-prompts/` directory.

---

## 📝 Example Config & Prompt Files

To help you get started safely, this repo includes example config and prompt files:

- `setup/wrtr.config.example.md`
- `setup/main-prompt.example.txt`

**How to use:**
1. Copy or rename `setup/wrtr.config.example.md` to `setup/wrtr.config.md` and fill in your company/blog details.
2. Copy or rename `setup/main-prompt.example.txt` to `setup/main-prompt.txt` and customize your main prompt style.

> **Note:** The real config and prompt files are ignored by git, so your sensitive info stays private! 🎉