import fs from 'fs';
import path from 'path';
import ora from 'ora';
import sharp from 'sharp';
import dotenv from 'dotenv';
import axios from 'axios';
import { fileURLToPath } from 'url';
import { GENERAL_IMAGE_DIR, PROMPTS_DIR, WEBP_QUALITY, WEBP_WIDTH, WEBP_HEIGHT } from './setup/system-prompts/config-loader';

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

// Use the prompt template from file
function buildImagePrompt(description: string): string {
  return promptTemplate.replace(/{{prompt}}/g, description);
}

async function generateAndSaveImage(description: string) {
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
  const imagesDir = GENERAL_IMAGE_DIR;
  // Only create the directory if using the default path, otherwise fail if it doesn't exist
  const isDefaultImageDir = imagesDir.endsWith(path.join('wrtr', 'images'));
  if (isDefaultImageDir) {
    fs.mkdirSync(imagesDir, { recursive: true });
  } else if (!fs.existsSync(imagesDir)) {
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
  const descriptions = process.argv.slice(2);
  if (descriptions.length === 0) {
    ora().fail('Please provide one or more image descriptions as CLI arguments.');
    process.exit(1);
  }
  for (const desc of descriptions) {
    await generateAndSaveImage(desc);
  }
  ora().succeed('All images processed! 🎉');
}

main().catch((err) => {
  ora().fail('Something went wrong: ' + err.message);
  process.exit(1);
}); 