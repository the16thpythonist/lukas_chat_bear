# Manual Test Scripts

This directory contains manual test scripts for validating real API integrations.

## Image Generation Test

`test_image_generation_manual.py` - Test real DALL-E image generation

### Prerequisites

1. OpenAI API key configured in `.env`:
   ```bash
   OPENAI_API_KEY=sk-...
   ```

2. Activate virtual environment:
   ```bash
   source .venv/bin/activate
   ```

### Usage

```bash
# Generate seasonal image (based on current date)
python scripts/test_image_generation_manual.py

# Generate autumn-themed image
python scripts/test_image_generation_manual.py --theme autumn

# Generate Halloween image
python scripts/test_image_generation_manual.py --occasion halloween

# Generate winter Christmas image
python scripts/test_image_generation_manual.py --theme winter --occasion christmas
```

### What It Does

1. ✅ Verifies OpenAI API key is configured
2. 📊 Initializes database
3. 🎨 Generates contextual prompt based on theme/occasion
4. ✔️ Validates prompt
5. 🖼️ **Generates real image using DALL-E API** (~$0.04 cost)
6. 💾 Downloads and saves image to `test_images/`
7. 📝 Displays result details (prompt, URL, cost, duration)

### Output

Images are saved to: `test_images/bear_image_YYYYMMDD_HHMMSS.png`

### Cost Warning

⚠️ **This script makes real API calls to DALL-E 3 and costs approximately $0.04 per image.**

Use sparingly for manual verification only.

### Available Options

**Themes**: spring, summer, autumn, winter, flowers, snow, beach, camping, etc.

**Occasions**:
- `halloween` - October 31
- `christmas` - December 25
- `thanksgiving` - November ~25
- `valentines` - February 14
- `new_year` - January 1
- `st_patricks` - March 17
- `independence_day` - July 4
- `new_years_eve` - December 31

### Example Output

```
================================================================================
DALL-E Image Generation Manual Test
================================================================================

✅ OpenAI API key found: sk-proj-R9...
📊 Initializing database...
✅ Database initialized

📁 Output directory: /path/to/test_images

🖼️  Initializing image service...
✅ Image service initialized

🎨 Generating contextual prompt...
Theme: autumn
Occasion: halloween
Month/Day: 10/31
Prompt: A friendly bear wearing a cute costume, surrounded by pumpkins and autumn leaves...

✔️  Validating prompt...
✅ Prompt is valid

🎨 Generating image with DALL-E 3...
⚠️  This will cost approximately $0.04
⏳ Please wait (this may take 10-30 seconds)...

✅ Image generated successfully!

--------------------------------------------------------------------------------
RESULT
--------------------------------------------------------------------------------
Image ID: 123
Status: generated
Prompt: A friendly bear wearing a cute costume...
URL: https://oaidalleapiprodscus.blob.core.windows.net/...
Cost: $0.0400
Duration: 12.34s
Created: 2025-10-27 14:30:00

💾 Downloading image...
✅ Image saved to: test_images/bear_image_20251027_143000.png

File size: 892.45 KB

Caption: Happy Halloween! Don't worry, I'm a friendly bear!

================================================================================
✅ TEST PASSED
================================================================================
```
