import fs from 'fs';
import path from 'path';
import ora from 'ora';
import sharp from 'sharp';
import dotenv from 'dotenv';
import axios from 'axios';
import { fileURLToPath } from 'url';
import { GENERAL_IMAGE_DIR, WEBP_QUALITY, WEBP_WIDTH, WEBP_HEIGHT, IMAGE_PROMPT_TEMPLATE } from './setup/system-prompts/config-loader';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

dotenv.config();

// Utility: Slugify a string for filenames
function slugify(text: string): string {
  return text
    .toString()
    .toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/[^a-z0-9\-]/g, '')
    .replace(/-+/g, '-')
    .replace(/^-+|-+$/g, '');
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

// Use the prompt template from config
function buildImagePrompt(description: string): string {
  return IMAGE_PROMPT_TEMPLATE.replace(/{{PROMPT}}/gi, description);
}

async function ensureImagesDir() {
  // Default fallback directory inside wrtr/
  const defaultImagesDir = path.join(__dirname, 'images');
  let imagesDir = GENERAL_IMAGE_DIR;
  let usedDefault = false;

  if (!fs.existsSync(GENERAL_IMAGE_DIR)) {
    ora().warn(`Image directory does not exist: ${GENERAL_IMAGE_DIR}. Will use default: ${defaultImagesDir}`);
    imagesDir = defaultImagesDir;
    usedDefault = true;
  }
  if (usedDefault) {
    if (!fs.existsSync(imagesDir)) {
      fs.mkdirSync(imagesDir, { recursive: true });
      ora().info(`Created default image directory: ${imagesDir}`);
    }
    ora().succeed('Default image folder created and will be used for this run! 🎉');
  }
  return imagesDir;
}

async function generateAndSaveImage(description: string, imagesDir: string) {
  const prompt = buildImagePrompt(description);
  const spinner = ora(`Generating image for: "${description}"`).start();
  let b64Image = '';
  try {
    b64Image = await callOpenAIImageAPI(prompt);
    spinner.succeed(`Image generated for: "${description}"`);
  } catch (err: any) {
    spinner.fail(`OpenAI image generation failed for: "${description}"`);
    console.error(err.message);
    return;
  }

  // Optimize and save the image
  // Only create the directory if using the default path, otherwise fail if it doesn't exist
  const isDefaultImageDir = imagesDir.endsWith(path.join('wrtr', 'images'));
  if (!isDefaultImageDir && !fs.existsSync(imagesDir)) {
    ora().fail(`Custom image directory does not exist: ${imagesDir}. Please create it manually.`);
    throw new Error(`Custom image directory does not exist: ${imagesDir}`);
  }
  const timestamp = Date.now();
  // Use only the first three words of the description for the filename
  const firstThreeWords = description.split(/\s+/).slice(0, 3).join(' ');
  const filename = `${slugify(firstThreeWords)}-${timestamp}.webp`;
  const imagePath = path.join(imagesDir, filename);
  const saveSpinner = ora(`Optimizing and saving image: ${filename}`).start();
  try {
    const imageBuffer = Buffer.from(b64Image, 'base64');
    const cropped = await sharp(imageBuffer)
      .resize({ width: WEBP_WIDTH, height: WEBP_HEIGHT, fit: 'cover' })
      .webp({ quality: WEBP_QUALITY })
      .toBuffer();
    fs.writeFileSync(imagePath, new Uint8Array(cropped));
    saveSpinner.succeed(`Image saved: /images/${filename}`);
  } catch (err: any) {
    saveSpinner.fail(`Failed to process or save image: ${filename}`);
    console.error(err.message);
  }
}

async function main() {
  const imagesDir = await ensureImagesDir();
  const descriptions = process.argv.slice(2);
  if (descriptions.length === 0) {
    ora().fail('Please provide one or more image descriptions as CLI arguments.');
    process.exit(1);
  }
  for (const desc of descriptions) {
    await generateAndSaveImage(desc, imagesDir);
  }
  ora().succeed('All images processed! 🎉');
}

main().catch((err) => {
  ora().fail('Something went wrong: ' + err.message);
  process.exit(1);
}); 