import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import ora from 'ora';
import sharp from 'sharp';
import dotenv from 'dotenv';
import axios from 'axios';
import { fileURLToPath } from 'url';
import { BLOG_CONTENT_DIR, BLOG_IMAGE_DIR, PROMPTS_DIR, WEBP_QUALITY, WEBP_WIDTH, WEBP_HEIGHT } from './setup/system-prompts/config-loader';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

dotenv.config();

const promptTemplatePath = path.join(PROMPTS_DIR, 'openai-image.txt');
let promptTemplate = '';
try {
  promptTemplate = fs.readFileSync(promptTemplatePath, 'utf8');
} catch (err) {
  ora().fail('Could not read OpenAI image prompt template.');
  process.exit(1);
}

// Utility: Find the latest .mdx file in blog
function getLatestBlogFile(): string | null {
  const blogDir = BLOG_CONTENT_DIR;
  const files = fs.readdirSync(blogDir)
    .filter(f => f.endsWith('.mdx'))
    .map(f => ({
      file: f,
      mtime: fs.statSync(path.join(blogDir, f)).mtime.getTime(),
    }))
    .sort((a, b) => b.mtime - a.mtime);
  return files.length > 0 ? path.join(blogDir, files[0].file) : null;
}

// Utility: Generate image with OpenAI
async function callOpenAIImageAPI(prompt: string): Promise<string> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) throw new Error('Missing OPENAI_API_KEY in .env');
  const url = 'https://api.openai.com/v1/images/generations';
  const payload = {
    model: 'gpt-image-1',
    prompt,
    n: 1,
    size: '1536x1024',
  };
  const headers = {
    'Authorization': `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  };
  const response = await axios.post(url, payload, { headers });
  if (response.data && response.data.data && response.data.data[0]?.b64_json) {
    return response.data.data[0].b64_json;
  }
  throw new Error('No image data returned from OpenAI image API');
}

// Utility: Use the same image prompt style as main blog script
function buildImagePrompt(description: string): string {
  return promptTemplate.replace(/{{prompt}}/g, description);
}

async function main() {
  const spinner = ora('Finding latest blog post...').start();
  const blogFile = getLatestBlogFile();
  if (!blogFile) {
    spinner.fail('😢 No blog posts found! There are no .mdx files in your blog directory. Please create a blog post first.');
    process.exit(0);
  }
  spinner.succeed(`Found latest blog: ${path.basename(blogFile)}`);

  const fileContent = fs.readFileSync(blogFile, 'utf8');
  const { data: frontmatter } = matter(fileContent);
  if (!frontmatter.image) {
    ora().fail('No image field found in the blog frontmatter.');
    process.exit(1);
  }
  if (!frontmatter.title) {
    ora().fail('No title field found in the blog frontmatter.');
    process.exit(1);
  }

  const newDescription = process.argv[2];
  if (!newDescription) {
    ora().fail('Please provide a new image description as a CLI argument.');
    process.exit(1);
  }

  // Optional: custom image path as third argument
  const customImagePathArg = process.argv[3];
  let imagePath: string;
  if (customImagePathArg) {
    // If absolute, use as is; if relative, resolve from project root
    imagePath = path.isAbsolute(customImagePathArg)
      ? customImagePathArg
      : path.join(process.cwd(), customImagePathArg);
    ora().info(`Custom image path provided: ${imagePath}`);
  } else {
    imagePath = path.join(BLOG_IMAGE_DIR, path.basename(frontmatter.image));
  }

  const imagePrompt = buildImagePrompt(newDescription);
  const imageSpinner = ora('Generating new hero image with OpenAI...').start();
  let b64Image = '';
  try {
    b64Image = await callOpenAIImageAPI(imagePrompt);
    imageSpinner.succeed('New hero image generated!');
  } catch (err: any) {
    imageSpinner.fail('OpenAI image generation failed.');
    console.error(err.message);
    process.exit(1);
  }

  // Optimize and overwrite the image
  const saveSpinner = ora('Optimizing and saving new hero image...').start();
  try {
    const imageBuffer = Buffer.from(b64Image, 'base64');
    fs.mkdirSync(path.dirname(imagePath), { recursive: true });
    const cropped = await sharp(imageBuffer)
      .resize({ width: WEBP_WIDTH, height: WEBP_HEIGHT, fit: 'cover' })
      .webp({ quality: WEBP_QUALITY })
      .toBuffer();
    fs.writeFileSync(imagePath, new Uint8Array(cropped));
    saveSpinner.succeed(`Image replaced: ${imagePath}`);
  } catch (err: any) {
    saveSpinner.fail('Failed to process or save new image.');
    console.error(err.message);
    process.exit(1);
  }
  ora().succeed('Blog hero image updated successfully! 🎉');
}

main().catch((err) => {
  ora().fail('Something went wrong: ' + err.message);
  process.exit(1);
}); 