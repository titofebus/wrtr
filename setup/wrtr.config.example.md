---
# =========================
# WRTR Project Configuration (Example)
# =========================
#
# Copy this file to wrtr.config.md and edit the values below to update your project/company/blog settings.
# All paths are relative to the project root.
#
# Comments (like these) explain what each field does!
#
company:
  type: CRM                # The type of company/product (e.g., CRM, SaaS, Agency)
  name: ExampleCo          # Your company or product name
  target: your audience    # Your main audience or customer type
  competitors:             # List of your main competitors
    - Competitor1
    - Competitor2
  author: Your Name        # Default author name for blog posts
  main_features:           # List your product's main features (for prompts, marketing, etc.)
    - feature 1
    - feature 2
blog:
  content_dir: src/content/blog           # Where blog posts (.mdx/.md) are saved
  image_dir: public/blog                  # Where hero images for blog posts are saved
  general_image_dir: public/images        # Where general/generated images are saved
  prompts_dir: wrtr/setup/system-prompts  # Where prompt templates are stored (internal use)
  webp_quality: 80                        # Compression quality (0-100, higher is better quality, default 80)
  webp_size: 1536x1024                    # Size for webp images in WIDTHxHEIGHT format (default 1536x1024)
  default_frontmatter:                    # Default frontmatter for new blog posts
    title: ""                             # Blog post title (leave blank for script to fill)
    description: ""                       # Blog post description (leave blank for script to fill)
    pubDate: today                        # Publication date ("today" will be replaced automatically)
    image: ""                             # Path to main image/thumbnail (script will fill, e.g. /blog/slug-date.webp)
    author: Your Name                     # Author name (usually matches company.author)
    updatedDate: ""                       # Last updated date (optional)
    heroImage: ""                         # Path to a large hero image (optional)
  image_prompt_template: |
    Create an illustration inspired by Hokusai's silhouette style, blending a dreamlike, minimalistic, and uplifting atmosphere. Use a soft, muted palette limited to just three colors: light brown, muted brown, and one additional complementary neutral. The artwork should have a subtle grainy texture throughout, blurred elements to is, with gentle fades and hand-drawn, sketch-like strokes that feel organic and imperfect.

    The scene should depict the peaceful silhouette of '{{PROMPT}}'. it should feel natural and serene, as if they're lost in a positive flow of creativity. Faces should not be recongnizable only silhouettes. The overall mood should feel light, calm, and slightly nostalgic — like a distant memory or a quiet moment captured in time.
---

# WRTR Project Configuration 🎉

Welcome! This is your one-stop config file for the WRTR project. Edit the values above to update your project/company/blog settings.

- All paths are relative to the project root.
- You can add more features or competitors as needed.
- The `pubDate` field will be set to today's date automatically by the scripts.
- Frontmatter fields should match the required/optional fields in writer-rules.mdc. 