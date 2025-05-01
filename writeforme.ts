import axios from 'axios';
import sharp from 'sharp';
import * as fs from 'fs';
import * as path from 'path';
import dotenv from 'dotenv';
import { fileURLToPath } from 'url';
import { dirname as pathDirname } from 'path';
import ora from 'ora';
import {
  BLOG_CONTENT_DIR,
  BLOG_IMAGE_DIR,
  PROMPTS_DIR,
  COMPANY_TYPE,
  COMPANY_NAME,
  COMPANY_TARGET,
  COMPANY_COMPETITORS,
  COMPANY_MAIN_FEATURES,
  DEFAULT_BLOG_FRONTMATTER,
  WEBP_QUALITY,
  WEBP_WIDTH,
  WEBP_HEIGHT
} from './setup/system-prompts/config-loader';
import type { BlogFrontmatter } from './setup/system-prompts/config-loader';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = pathDirname(__filename);

/**
 * Blog Automation Script – Quick Start Guide 🚀
 *
 * Usage:
 *   pnpm exec tsx wrtr/writeforme.ts "Your Blog Title" "A short description of your blog post." [--skip-perplexity]
 *
 * Arguments:
 *   1. Blog Title (optional)
 *   2. Blog Description (optional)
 *   3. Keywords (optional)
 *   4. --skip-perplexity (optional): If present, skips the Perplexity research step and generates the article using only OpenAI.
 *
 * Example:
 *   pnpm exec tsx wrtr/writeforme.ts "How to Automate Blogging with AI" "A step-by-step guide." --skip-perplexity
 */

// Utility: Slugify a string for filenames/URLs
function slugify(text: string): string {
  return text
    .toString()
    .toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/[^a-z0-9\-]/g, '')
    .replace(/\-+/g, '-')
    .replace(/^-+|-+$/g, '');
}

// Utility: Read and fill a prompt template
function fillPromptTemplate(filePath: string, variables: Record<string, string>): string {
  let template = fs.readFileSync(filePath, 'utf8');
  for (const [key, value] of Object.entries(variables)) {
    const regex = new RegExp(`{{${key}}}`, 'g');
    template = template.replace(regex, value);
  }
  return template;
}

// Utility: Format date as 'MMMM DD, YYYY'
function formatDate(date: Date): string {
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: '2-digit',
  });
}

type BlogMetadata = {
  title: string;
  description: string;
  image: string;
  // add any other fields you expect
};

const mainPromptPath = path.join(__dirname, 'setup', 'main-prompt.txt');
let mainPrompt = '';
try {
  mainPrompt = fs.readFileSync(mainPromptPath, 'utf8');
} catch (err) {
  console.error('😢 Could not read main prompt template.');
  mainPrompt = '';
}

const moonSpinner = {
  interval: 120,
  frames: ['[    ]','[=   ]','[==  ]','[=== ]','[ ===]','[  ==]','[   =]','[    ]']
};

export async function callPerplexityAPI(prompt: string): Promise<any> {
  const apiKey = process.env.PERPLEXITY_API_KEY;
  if (!apiKey) throw new Error('Missing PERPLEXITY_API_KEY in .env');
  const url = 'https://api.perplexity.ai/chat/completions';
  const payload = {
    model: 'sonar-pro',
    messages: [
      {
        role: 'system',
        content: 'Be precise and concise. Use up-to-date, factual information from the web. Return a comprehensive research summary on the following blog topic.'
      },
      {
        role: 'user',
        content: prompt
      }
    ],
    web_search_options: {
      search_context_size: 'high'
    },
    max_tokens: 4096,
    temperature: 0.9
  };
  const headers = {
    'Authorization': `Bearer ${apiKey}`,
    'Content-Type': 'application/json'
  };
  const response = await axios.post(url, payload, { headers });
  return response.data;
}

export async function callOpenAIArticleAPI(prompt: string): Promise<any> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) throw new Error('Missing OPENAI_API_KEY in .env');
  const url = 'https://api.openai.com/v1/chat/completions';
  const payload = {
    model: 'o3',
    messages: [
      {
        role: 'system',
        content: mainPrompt + "\n\nYou are a senior technical SEO writer. Write a long-form, in-depth, markdown-formatted blog article based on the following research. Use only '##' and lower for headings, never '#'."
      },
      {
        role: 'user',
        content: prompt
      }
    ],
    max_completion_tokens: 8192
  };
  const headers = {
    'Authorization': `Bearer ${apiKey}`,
    'Content-Type': 'application/json'
  };
  try {
    const response = await axios.post(url, payload, { headers });
    return response.data;
  } catch (err: any) {
    if (err.response) {
      console.error('😢 OpenAI article generation failed:', err.response.data);
    }
    throw err;
  }
}

export async function callOpenAIMetadataAPI(prompt: string): Promise<any> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) throw new Error('Missing OPENAI_API_KEY in .env');
  const url = 'https://api.openai.com/v1/chat/completions';
  const payload = {
    model: 'gpt-4.1',
    messages: [
      {
        role: 'system',
        content: 'Extract blog metadata as JSON. Only respond with the JSON.'
      },
      {
        role: 'user',
        content: prompt
      }
    ],
    max_completion_tokens: 8192
  };
  const headers = {
    'Authorization': `Bearer ${apiKey}`,
    'Content-Type': 'application/json'
  };
  try {
    const response = await axios.post(url, payload, { headers });
    return response.data;
  } catch (err: any) {
    if (err.response) {
      console.error('😢 OpenAI metadata extraction failed:', err.response.data);
    }
    throw err;
  }
}

export async function callOpenAIImageAPI(prompt: string): Promise<string> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) throw new Error('Missing OPENAI_API_KEY in .env');
  const url = 'https://api.openai.com/v1/images/generations';
  const payload = {
    model: 'gpt-image-1',
    prompt,
    n: 1,
    size: '1536x1024'
  };
  const headers = {
    'Authorization': `Bearer ${apiKey}`,
    'Content-Type': 'application/json'
  };
  const response = await axios.post(url, payload, { headers });
  if (response.data && response.data.data && response.data.data[0]?.b64_json) {
    return response.data.data[0].b64_json;
  }
  throw new Error('No image data returned from OpenAI image API');
}

async function main() {
  // Only create directories if using default paths
  const defaultBlogDir = path.join(__dirname, 'blog');
  const defaultBlogImagesDir = path.join(__dirname, 'blog-images');
  if (BLOG_CONTENT_DIR === defaultBlogDir) {
    fs.mkdirSync(BLOG_CONTENT_DIR, { recursive: true });
  }
  if (BLOG_IMAGE_DIR === defaultBlogImagesDir) {
    fs.mkdirSync(BLOG_IMAGE_DIR, { recursive: true });
  }

  // 1. Get blog title & description (placeholder for now)
  const title = process.argv[2] || 'Sample Blog Title';
  const description = process.argv[3] || 'Sample blog description.';
  // Add support for keywords as an optional 4th argument
  const keywordsString = process.argv[4] || '';
  // Add skipPerplexity flag
  const skipPerplexity = process.argv.includes('--skip-perplexity');
  const slug = slugify(title);
  const today = new Date().toISOString().split('T')[0];

  let researchSummary = '';
  let citations: string[] = [];

  if (!skipPerplexity) {
    // 2. Load and fill Perplexity prompt template
    const perplexityPromptPath = path.join(PROMPTS_DIR, 'perplexity.txt');
    const formattedToday = formatDate(new Date());
    const perplexityPrompt = fillPromptTemplate(perplexityPromptPath, {
      KEYWORD: title,
      DESCRIPTION: description,
      KEYWORDS: keywordsString,
      TODAY: formattedToday,
      COMPANY_TYPE,
      COMPANY_NAME,
      COMPANY_TARGET,
      COMPANY_COMPETITORS: COMPANY_COMPETITORS.join(', '),
      COMPANY_MAIN_FEATURES: COMPANY_MAIN_FEATURES.join(', '),
    });

    const perplexitySpinner = ora({ text: 'Calling Perplexity API for research...', spinner: moonSpinner }).start();
    try {
      const perplexityData = await callPerplexityAPI(perplexityPrompt);
      perplexitySpinner.succeed('Perplexity research complete!');
      // 4. Extract research summary and citations
      try {
        if (perplexityData.choices && perplexityData.choices[0]?.message?.content) {
          researchSummary = perplexityData.choices[0].message.content;
        } else {
          throw new Error('No research summary found in Perplexity response.');
        }
        // Try to extract citations or sources if present
        if (perplexityData.choices[0].message.citations) {
          citations = perplexityData.choices[0].message.citations;
        } else if (perplexityData.choices[0].message.sources) {
          citations = perplexityData.choices[0].message.sources;
        }
      } catch (err) {
        perplexitySpinner.fail('😢 Failed to extract research summary or citations.');
        console.error('😢 Failed to extract research summary or citations:', err);
      }
    } catch (err) {
      perplexitySpinner.fail('😢 Perplexity API call failed.');
      console.error('😢 Perplexity API call failed:', err);
    }
  } else {
    console.log('\n[Main] Skipping Perplexity step as requested.');
    researchSummary = '';
    citations = [];
  }

  // 5. Load and fill OpenAI article prompt template
  const openaiArticlePromptPath = path.join(PROMPTS_DIR, 'openai-article.txt');
  const openaiArticlePrompt = fillPromptTemplate(openaiArticlePromptPath, {
    KEYWORD: title,
    DESCRIPTION: description,
    KEYWORDS: keywordsString,
    'PERPLEXITY DATA': researchSummary,
    'PERPLEXITY CITATIONS': citations.join('\n'),
    COMPANY_MAIN_FEATURES: COMPANY_MAIN_FEATURES.join(', '),
  });

  const articleSpinner = ora({ text: 'Generating article with OpenAI...', spinner: moonSpinner }).start();
  let openaiArticleData;
  try {
    openaiArticleData = await callOpenAIArticleAPI(openaiArticlePrompt);
    articleSpinner.succeed('Article generated!');
  } catch (err) {
    articleSpinner.fail('😢 OpenAI article generation failed.');
    console.error('😢 OpenAI article generation failed:', err);
    return;
  }
  let articleMarkdown = '';
  try {
    if (openaiArticleData.choices && openaiArticleData.choices[0]?.message?.content) {
      articleMarkdown = openaiArticleData.choices[0].message.content;
    } else {
      throw new Error('No article content found in OpenAI response.');
    }
  } catch (err) {
    articleSpinner.fail('😢 Failed to extract article markdown.');
    console.error('😢 Failed to extract article markdown:', err);
  }

  // 7. Load and fill OpenAI metadata prompt template
  const openaiMetadataPromptPath = path.join(PROMPTS_DIR, 'openai-metadata.txt');
  const formattedShortDate = new Date().toLocaleDateString('en-US', { month: '2-digit', day: '2-digit', year: 'numeric' });

  // Dynamically build JSON structure and variables from BlogFrontmatter config
  const frontmatterFields = Object.keys(DEFAULT_BLOG_FRONTMATTER);
  const jsonStructure = `{
${frontmatterFields.map(field => `  "${field}": "{{${field.toUpperCase()}}}"`).join(',\n')}
}`;

  // Build variables object dynamically
  const variables: Record<string, string> = {
    KEYWORD: title.toUpperCase(),
    DESCRIPTION: description.toUpperCase(),
    KEYWORDS: keywordsString.toUpperCase(),
    'formatDate(now; \'MM-DD-YYYY\')': formattedShortDate,
    'o3 Blog': articleMarkdown,
    JSON_STRUCTURE: jsonStructure,
  };
  frontmatterFields.forEach(field => {
    variables[field.toUpperCase()] = (DEFAULT_BLOG_FRONTMATTER as any)[field];
  });

  const openaiMetadataPrompt = fillPromptTemplate(openaiMetadataPromptPath, variables);

  const metadataSpinner = ora({ text: 'Extracting metadata with OpenAI...', spinner: moonSpinner }).start();
  let openaiMetadataData;
  try {
    openaiMetadataData = await callOpenAIMetadataAPI(openaiMetadataPrompt);
    metadataSpinner.succeed('Metadata extracted!');
  } catch (err) {
    metadataSpinner.fail('😢 OpenAI metadata extraction failed.');
    console.error('😢 OpenAI metadata extraction failed:', err);
    return;
  }
  let metadata: BlogMetadata | null = null;
  try {
    if (openaiMetadataData.choices && openaiMetadataData.choices[0]?.message?.content) {
      // Try to parse JSON from the response
      const raw = openaiMetadataData.choices[0].message.content.replace(/```json|```/g, '').trim();
      try {
        metadata = JSON.parse(raw);
      } catch (err) {
        console.error('RAW METADATA RESPONSE:', raw);
        throw err;
      }
    } else {
      throw new Error('No metadata content found in OpenAI response.');
    }
  } catch (err) {
    metadataSpinner.fail('😢 Failed to extract or parse metadata.');
    console.error('😢 Failed to extract or parse metadata:', err);
  }

  // 9. Create MDX frontmatter and save .mdx file
  if (!metadata) {
    console.error('😢 No metadata available, cannot create MDX file.');
    return;
  }
  // Use the BlogFrontmatter config for frontmatter fields
  const frontmatter: BlogFrontmatter = {
    title: metadata.title || DEFAULT_BLOG_FRONTMATTER.title,
    description: metadata.description || DEFAULT_BLOG_FRONTMATTER.description,
    pubDate: today,
    image: `/blog-images/${slug}-${today}.webp`,
    author: DEFAULT_BLOG_FRONTMATTER.author,
  };
  const mdxFrontmatter = `---\ntitle: "${frontmatter.title}"\ndescription: "${frontmatter.description}"\npubDate: "${frontmatter.pubDate}"\nimage: "${frontmatter.image}"\nauthor: "${frontmatter.author}"\n---\n`;
  const mdxContent = mdxFrontmatter + '\n' + articleMarkdown;
  const mdxFilePath = path.join(BLOG_CONTENT_DIR, `${slug}-${today}.mdx`);

  const fileSpinner = ora({ text: 'Saving MDX file...', spinner: moonSpinner }).start();
  // Ensure the blog directory exists before writing
  const isDefaultBlogDir = BLOG_CONTENT_DIR.endsWith(path.join('wrtr', 'blog'));
  if (isDefaultBlogDir) {
    fs.mkdirSync(path.dirname(mdxFilePath), { recursive: true });
  } else if (!fs.existsSync(path.dirname(mdxFilePath))) {
    fileSpinner.fail(`Custom blog directory does not exist: ${path.dirname(mdxFilePath)}. Please create it manually.`);
    throw new Error(`Custom blog directory does not exist: ${path.dirname(mdxFilePath)}`);
  }

  try {
    fs.writeFileSync(mdxFilePath, mdxContent, 'utf8');
    fileSpinner.succeed(`🎉 MDX file created: ${mdxFilePath}`);
  } catch (err) {
    fileSpinner.fail('😢 Failed to write MDX file.');
    console.error('😢 Failed to write MDX file:', err);
  }

  // 10. Load and fill OpenAI image prompt template
  if (!metadata?.image) {
    console.error('😢 No image suggestion in metadata, cannot generate image.');
    return;
  }
  const openaiImagePromptPath = path.join(PROMPTS_DIR, 'openai-image.txt');
  const openaiImagePrompt = fillPromptTemplate(openaiImagePromptPath, {
    PROMPT: metadata.image,
  });

  const imageSpinner = ora({ text: 'Generating hero image with OpenAI...', spinner: moonSpinner }).start();
  let b64Image = '';
  try {
    b64Image = await callOpenAIImageAPI(openaiImagePrompt);
    imageSpinner.succeed('Hero image generated!');
  } catch (err) {
    imageSpinner.fail('😢 OpenAI image generation failed.');
    console.error('😢 OpenAI image generation failed:', err);
    return;
  }

  // 12. Process and save image (crop to landscape aspect ratio, convert to webp)
  const imageBuffer = Buffer.from(b64Image, 'base64');
  const imageFilePath = path.join(BLOG_IMAGE_DIR, `${slug}-${today}.webp`);
  const saveImageSpinner = ora({ text: 'Saving hero image...', spinner: moonSpinner }).start();
  // Ensure the image directory exists before writing
  const isDefaultImageDir = BLOG_IMAGE_DIR.endsWith(path.join('wrtr', 'blog-images'));
  if (isDefaultImageDir) {
    fs.mkdirSync(path.dirname(imageFilePath), { recursive: true });
  } else if (!fs.existsSync(path.dirname(imageFilePath))) {
    saveImageSpinner.fail(`Custom image directory does not exist: ${path.dirname(imageFilePath)}. Please create it manually.`);
    throw new Error(`Custom image directory does not exist: ${path.dirname(imageFilePath)}`);
  }
  try {
    // Crop to landscape aspect ratio (1536x1024)
    const cropped = await sharp(imageBuffer)
      .resize({ width: WEBP_WIDTH, height: WEBP_HEIGHT, fit: 'cover' })
      .webp({ quality: WEBP_QUALITY })
      .toBuffer();
    // Buffer is compatible with fs.writeFileSync, but cast to Uint8Array for strict TS
    fs.writeFileSync(imageFilePath, new Uint8Array(cropped));
    saveImageSpinner.succeed(`🎉 Image file created: ${imageFilePath}`);
  } catch (err) {
    saveImageSpinner.fail('😢 Failed to process or save image.');
    console.error('😢 Failed to process or save image:', err);
  }
  // All done!
  ora().succeed('All steps complete! Blog post and image are ready! 🎉');
}

// Only run main() if this file is executed directly
main().catch((err) => {
  console.error('😢 Automation failed:', err);
  process.exit(1);
});
