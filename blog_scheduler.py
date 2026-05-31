"""
Blog Scheduler - Runs daily at 6 AM US Central Time to generate and publish new blog posts
"""
import os
import sys
import time
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from pymongo import MongoClient
import openai
import json
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configure logging
logging.basicConfig(
    filename="blog_scheduler.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

load_dotenv()

# MongoDB setup
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
client = MongoClient(MONGODB_URI)
db = client.inshora
blog_collection = db.blog_posts
scheduler_logs_collection = db.scheduler_logs

# OpenAI setup
openai.api_key = os.getenv("OPENAI_API_KEY")

# SMTP configuration
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_SECURE = os.getenv("SMTP_SECURE", "false").lower() == "true"
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO")

# Lock mechanism to prevent duplicate runs
LOCK_FILE = "scheduler.lock"
BLOG_RETENTION_DAYS = int(os.getenv("BLOG_RETENTION_DAYS", "60"))

def is_locked():
    """Check if scheduler lock file exists"""
    return os.path.exists(LOCK_FILE)

def acquire_lock():
    """Acquire scheduler lock"""
    try:
        with open(LOCK_FILE, "w") as f:
            f.write(str(datetime.utcnow().timestamp()))
        logger.info("Scheduler lock acquired")
        return True
    except Exception as e:
        logger.error(f"Failed to acquire lock: {e}", exc_info=True)
        return False

def release_lock():
    """Release scheduler lock"""
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
            logger.info("Scheduler lock released")
    except Exception as e:
        logger.error(f"Failed to release lock: {e}", exc_info=True)

def log_scheduler_run(status, attempts=1, error_message=None):
    """Log scheduler run to MongoDB for analytics and debugging"""
    try:
        central_tz = pytz.timezone('America/Chicago')
        today = datetime.now(central_tz).date()
        
        log_entry = {
            'date': str(today),
            'status': status,
            'attempts': attempts,
            'timestamp': datetime.utcnow(),
            'error_message': error_message
        }
        
        scheduler_logs_collection.insert_one(log_entry)
        logger.info(f"Scheduler run logged: {status} with {attempts} attempt(s)")
    except Exception as e:
        logger.error(f"Failed to log scheduler run: {e}", exc_info=True)

def send_email_notification(blog_data):
    """Send email notification after successful blog post"""
    try:
        if not all([SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, EMAIL_FROM, EMAIL_TO]):
            logger.warning("SMTP configuration incomplete. Skipping email notification.")
            print("✗ SMTP configuration incomplete. Skipping email notification.")
            return False

        # Create email message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"🚀 New Blog Post Published: {blog_data['title']}"
        msg['From'] = EMAIL_FROM
        msg['To'] = EMAIL_TO

        # Create HTML email body
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #0B1F8F;">🎉 New Blog Post Published!</h2>
                
                <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="color: #0B1F8F; margin-top: 0;">{blog_data['title']}</h3>
                    <p><strong>Category:</strong> {blog_data.get('category', 'Insurance Tips')}</p>
                    <p><strong>Author:</strong> {blog_data.get('author', 'Inshora AI')}</p>
                    <p><strong>Published:</strong> {blog_data.get('created_at', datetime.utcnow()).strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>

                <div style="margin: 20px 0;">
                    <h4 style="color: #0B1F8F;">Excerpt:</h4>
                    <p style="font-style: italic;">{blog_data.get('excerpt', 'No excerpt available')}</p>
                </div>

                <div style="margin: 20px 0;">
                    <h4 style="color: #0B1F8F;">Tags:</h4>
                    <p>{', '.join(blog_data.get('tags', []))}</p>
                </div>

                <div style="background: #0B1F8F; color: white; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <p style="margin: 0; text-align: center; font-size: 16px;">
                        <strong>Inshora Group - Your Trusted Insurance Partner</strong><br>
                        Call (713) 943-9985 for instant quotes
                    </p>
                </div>

                <p style="color: #666; font-size: 12px; text-align: center; margin-top: 30px;">
                    This is an automated notification from the Inshora Blog Scheduler.<br>
                    Generated at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
                </p>
            </div>
        </body>
        </html>
        """

        # Attach HTML body
        html_part = MIMEText(html_body, 'html')
        msg.attach(html_part)

        # Send email
        logger.info(f"Sending email notification to {EMAIL_TO}...")
        print(f"Sending email notification to {EMAIL_TO}...")

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            # Always use STARTTLS for Gmail on port 587
            if SMTP_PORT == 587:
                server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)

        logger.info("Email notification sent successfully")
        print("✓ Email notification sent successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to send email notification: {e}", exc_info=True)
        print(f"✗ Failed to send email notification: {e}")
        return False

def generate_blog_post():
    """Generate a blog post using OpenAI"""
    insurance_topics = [
        # Texas-Specific Insurance Topics
        "Texas Insurance Laws You Need to Know in 2024",
        "Minimum Car Insurance Requirements in Texas",
        "Texas Home Insurance vs. Flood Insurance: What You Need",
        "How Texas Weather Affects Your Insurance Rates",
        "Texas vs. Other States: Insurance Cost Comparison",
        "Texas Windstorm Insurance: Coastal Homeowner Guide",
        "Understanding Texas Two-Step Verification for Insurance Claims",
        "Texas Tornado Alley: Insurance Protection Guide",
        "Houston vs. Dallas: Insurance Rate Differences",
        "Texas Farm Bureau vs. Major Insurers: Which is Better?",
        "Austin Texas Insurance Guide: Complete Coverage",
        "San Antonio Insurance: Best Rates and Coverage",
        "Fort Worth Insurance: What You Need to Know",
        "El Paso Texas Insurance: Complete Guide",
        "Corpus Christi Insurance: Coastal Protection",
        
        # Auto Insurance Topics
        "How to Get Cheap Car Insurance in Texas",
        "Texas SR-22 Insurance: Complete Guide",
        "Full Coverage vs. Liability: What Texas Drivers Need",
        "How Your Credit Score Affects Texas Car Insurance Rates",
        "Best Car Insurance for New Texas Drivers",
        "Texas Car Insurance for High-Risk Drivers",
        "How to Lower Your Car Insurance Premium in Texas",
        "Texas Car Insurance Discounts You're Missing",
        "Rideshare Insurance in Texas: Uber/Lyft Driver Guide",
        "Classic Car Insurance in Texas: What You Need",
        "Texas Car Insurance for Teen Drivers",
        "Texas Car Insurance for Seniors",
        "Texas Car Insurance for Bad Credit",
        "Texas Car Insurance for DUI",
        "Texas Car Insurance for Sports Cars",
        "Texas Car Insurance for SUVs",
        "Texas Car Insurance for Electric Vehicles",
        "Texas Car Insurance for Trucks",
        "Texas Car Insurance for Luxury Cars",
        "Texas Car Insurance for Hybrid Vehicles",
        
        # Home Insurance Topics
        "Texas Home Insurance Cost: Complete Breakdown",
        "How to Choose the Right Home Insurance Coverage in Texas",
        "Texas Home Insurance Claims: Step-by-Step Guide",
        "Flood Insurance in Texas: Is It Worth It?",
        "Hurricane Season in Texas: Insurance Preparation Guide",
        "Texas Home Insurance for Older Homes",
        "How to Save on Texas Home Insurance Premiums",
        "Texas Mobile Home Insurance Guide",
        "Rental Property Insurance in Texas",
        "Texas Home Insurance Deductibles: How to Choose",
        "Texas Home Insurance for New Construction",
        "Texas Home Insurance for Historic Homes",
        "Texas Home Insurance for Condos",
        "Texas Home Insurance for Townhouses",
        "Texas Home Insurance for Vacation Homes",
        "Texas Home Insurance for Rental Properties",
        "Texas Home Insurance for Investment Properties",
        "Texas Home Insurance for Second Homes",
        "Texas Home Insurance for High-Value Homes",
        "Texas Home Insurance for Manufactured Homes",
        
        # Renters Insurance Topics
        "Why Texas Renters Need Insurance",
        "Texas Renters Insurance: What It Covers",
        "Cheap Renters Insurance in Texas",
        "Texas Renters Insurance vs. Landlord Insurance",
        "How to File a Renters Insurance Claim in Texas",
        "Texas Apartment Insurance: What You Need",
        "Roommate Insurance in Texas: How It Works",
        "Texas Renters Insurance for College Students",
        "Moving to Texas: Renters Insurance Checklist",
        "Texas Renters Insurance for Pet Owners",
        "Texas Renters Insurance for Furniture",
        "Texas Renters Insurance for Electronics",
        "Texas Renters Insurance for Jewelry",
        "Texas Renters Insurance for Bicycles",
        "Texas Renters Insurance for Musical Instruments",
        "Texas Renters Insurance for Sports Equipment",
        "Texas Renters Insurance for Cameras",
        "Texas Renters Insurance for Computers",
        "Texas Renters Insurance for Collectibles",
        "Texas Renters Insurance for Art",
        
        # Pet Insurance Topics
        "Best Pet Insurance in Texas",
        "Texas Pet Insurance: Is It Worth It?",
        "Dog Breeds That Affect Texas Home Insurance Rates",
        "Texas Pet Insurance Pre-Existing Conditions Guide",
        "How Pet Insurance Works in Texas",
        "Texas Pet Insurance for Multiple Pets",
        "Emergency Vet Bills in Texas: Insurance Coverage",
        "Texas Pet Insurance vs. Savings Account",
        "Best Pet Insurance for Dogs in Texas",
        "Best Pet Insurance for Cats in Texas",
        "Texas Pet Insurance for Puppies",
        "Texas Pet Insurance for Kittens",
        "Texas Pet Insurance for Senior Pets",
        "Texas Pet Insurance for Exotic Pets",
        "Texas Pet Insurance for Large Breed Dogs",
        "Texas Pet Insurance for Small Breed Dogs",
        "Texas Pet Insurance for Purebred Dogs",
        "Texas Pet Insurance for Mixed Breed Dogs",
        "Texas Pet Insurance for Rescue Dogs",
        "Texas Pet Insurance for Service Animals",
        
        # Business Insurance Topics
        "Texas Small Business Insurance Requirements",
        "Texas Workers' Compensation Insurance Guide",
        "Texas Business Insurance for Contractors",
        "Texas General Liability Insurance: What You Need",
        "Texas Professional Liability Insurance Guide",
        "Texas Business Owner's Policy (BOP) Explained",
        "Texas Restaurant Insurance: Complete Guide",
        "Texas Retail Business Insurance",
        "Texas Home-Based Business Insurance",
        "Texas Commercial Auto Insurance Guide",
        "Texas Business Insurance for Startups",
        "Texas Business Insurance for Freelancers",
        "Texas Business Insurance for Consultants",
        "Texas Business Insurance for Healthcare Providers",
        "Texas Business Insurance for Real Estate Agents",
        "Texas Business Insurance for Lawyers",
        "Texas Business Insurance for Accountants",
        "Texas Business Insurance for IT Companies",
        "Texas Business Insurance for Marketing Agencies",
        "Texas Business Insurance for Construction Companies",
        
        # Life Insurance Topics
        "Texas Life Insurance: How Much Do You Need?",
        "Term vs. Whole Life Insurance in Texas",
        "Texas Life Insurance for Seniors",
        "Texas Life Insurance with No Medical Exam",
        "How to Choose Life Insurance in Texas",
        "Texas Life Insurance for Families",
        "Texas Life Insurance for Single Parents",
        "Texas Life Insurance for Business Owners",
        "Texas Life Insurance Riders Explained",
        "Texas Life Insurance Cost Factors",
        "Texas Life Insurance for New Parents",
        "Texas Life Insurance for Newlyweds",
        "Texas Life Insurance for Stay-at-Home Parents",
        "Texas Life Insurance for Retirees",
        "Texas Life Insurance for High Net Worth",
        "Texas Life Insurance for Estate Planning",
        "Texas Life Insurance for Mortgage Protection",
        "Texas Life Insurance for Income Replacement",
        "Texas Life Insurance for Final Expenses",
        "Texas Life Insurance for Children",
        
        # Bundle & Save Topics
        "How to Bundle Home and Auto Insurance in Texas",
        "Texas Insurance Bundling: Maximum Savings Guide",
        "Best Insurance Bundles in Texas 2024",
        "Texas Triple Bundle: Home, Auto, Life Insurance",
        "How Much Can You Save by Bundling in Texas?",
        "Texas Insurance Bundle Discounts Explained",
        "Best Companies for Insurance Bundling in Texas",
        "Texas Bundle vs. Separate Policies: Which is Better?",
        "Texas Insurance Bundle for New Homeowners",
        "How to Switch Insurance Bundles in Texas",
        "Texas Insurance Bundle for Families",
        "Texas Insurance Bundle for Seniors",
        "Texas Insurance Bundle for Young Drivers",
        "Texas Insurance Bundle for High-Value Homes",
        "Texas Insurance Bundle for Multiple Cars",
        "Texas Insurance Bundle for Luxury Vehicles",
        "Texas Insurance Bundle for Classic Cars",
        "Texas Insurance Bundle for RV Owners",
        "Texas Insurance Bundle for Boat Owners",
        "Texas Insurance Bundle for Motorcycle Owners",
        
        # Claims & Coverage Topics
        "How to File an Insurance Claim in Texas",
        "Texas Insurance Claims Process: Complete Guide",
        "What to Do After a Car Accident in Texas",
        "Texas Home Insurance Claims: Common Mistakes",
        "How Insurance Adjusters Work in Texas",
        "Texas Insurance Claim Denied: What to Do",
        "Texas Insurance Claim Timeline Explained",
        "How to Document Damage for Texas Insurance Claims",
        "Texas Insurance Claim Settlement Guide",
        "Texas Insurance Claims for Natural Disasters",
        "Texas Insurance Claims for Water Damage",
        "Texas Insurance Claims for Fire Damage",
        "Texas Insurance Claims for Theft",
        "Texas Insurance Claims for Vandalism",
        "Texas Insurance Claims for Storm Damage",
        "Texas Insurance Claims for Hail Damage",
        "Texas Insurance Claims for Wind Damage",
        "Texas Insurance Claims for Flood Damage",
        "Texas Insurance Claims for Personal Injury",
        "Texas Insurance Claims for Property Damage",
        
        # Money-Saving Topics
        "10 Ways to Lower Your Texas Insurance Premiums",
        "Texas Insurance Quotes: How to Compare",
        "Texas Insurance Discounts You Didn't Know About",
        "How to Get the Best Texas Insurance Rates",
        "Texas Insurance for Budget-Conscious Drivers",
        "Texas Insurance Payment Plans Explained",
        "Texas Insurance Deductibles: How to Choose",
        "Texas Insurance for Young Drivers: Cost-Saving Tips",
        "Texas Insurance for Seniors: Senior Discounts",
        "Texas Insurance: When to Switch Providers",
        "Texas Insurance for Low Income",
        "Texas Insurance for Students",
        "Texas Insurance for Military",
        "Texas Insurance for Veterans",
        "Texas Insurance for First-Time Buyers",
        "Texas Insurance for Non-Owners",
        "Texas Insurance for Occasional Drivers",
        "Texas Insurance for Low Mileage",
        "Texas Insurance for Good Drivers",
        "Texas Insurance for Safe Drivers",
        
        # Seasonal & Emergency Topics
        "Texas Hurricane Insurance Preparation Guide",
        "Texas Winter Storm Insurance: What You Need",
        "Texas Hail Damage Insurance Claims Guide",
        "Texas Flood Insurance: Before and After",
        "Texas Wildfire Insurance: Protection Guide",
        "Texas Tornado Insurance: What's Covered",
        "Texas Insurance for Natural Disasters",
        "Emergency Insurance Kit for Texas Residents",
        "Texas Insurance After Disaster Recovery",
        "Seasonal Insurance Tips for Texas Residents",
        "Texas Summer Insurance Tips",
        "Texas Winter Insurance Tips",
        "Texas Spring Insurance Tips",
        "Texas Fall Insurance Tips",
        "Texas Insurance for Monsoon Season",
        "Texas Insurance for Drought Conditions",
        "Texas Insurance for Heat Waves",
        "Texas Insurance for Freezing Weather",
        "Texas Insurance for Flash Floods",
        "Texas Insurance for Severe Storms",
        
        # Technology & Innovation Topics
        "Texas Insurance Apps: Best Digital Tools",
        "Telematics Insurance in Texas: How It Works",
        "Texas Insurance Chatbots: AI Assistance Guide",
        "Online Insurance Quotes in Texas: Pros and Cons",
        "Texas Insurance: Digital vs. Traditional",
        "Usage-Based Insurance in Texas",
        "Texas Insurance: Paperless Options Guide",
        "Texas Insurance: Online Claims Process",
        "Texas Insurance: Mobile App Benefits",
        "Future of Insurance in Texas: What to Expect",
        "Texas Insurance: Blockchain Technology",
        "Texas Insurance: AI and Machine Learning",
        "Texas Insurance: Big Data Analytics",
        "Texas Insurance: Internet of Things",
        "Texas Insurance: Smart Home Devices",
        "Texas Insurance: Wearable Technology",
        "Texas Insurance: Autonomous Vehicles",
        "Texas Insurance: Drones",
        "Texas Insurance: Virtual Reality",
        
        # Niche & Special Topics
        "Texas RV Insurance: Complete Guide",
        "Texas Motorcycle Insurance: What You Need",
        "Texas Boat Insurance: Watercraft Coverage",
        "Texas ATV Insurance: Off-Road Protection",
        "Texas Classic Car Insurance Guide",
        "Texas Electric Vehicle Insurance: Special Considerations",
        "Texas Commercial Truck Insurance",
        "Texas Rideshare Insurance: Uber/Lyft Guide",
        "Texas Delivery Driver Insurance",
        "Texas Construction Insurance Guide",
        "Texas Agriculture Insurance",
        "Texas Ranch Insurance",
        "Texas Farm Insurance",
        "Texas Equine Insurance",
        "Texas Livestock Insurance",
        "Texas Crop Insurance",
        "Texas Oil and Gas Insurance",
        "Texas Energy Insurance",
        "Texas Manufacturing Insurance",
        "Texas Technology Insurance",
        
        # Additional High-Traffic Topics
        "Best Insurance Companies in Texas 2024",
        "Cheapest Car Insurance in Texas",
        "Best Home Insurance Companies in Texas",
        "Top Rated Insurance in Texas",
        "Texas Insurance Reviews",
        "Texas Insurance Comparison",
        "Texas Insurance Calculator",
        "Texas Insurance Estimator",
        "Texas Insurance Quotes Online",
        "Texas Insurance Near Me",
        "Texas Insurance Agents",
        "Texas Insurance Brokers",
        "Texas Insurance Direct Writers",
        "Texas Insurance Captive Agents",
        "Texas Insurance Independent Agents",
        "Texas Insurance Online",
        "Texas Insurance Phone",
        "Texas Insurance Chat",
        "Texas Insurance Video",
        "Texas Insurance FAQ",
        
        # Local Texas City Guides
        "Sugar Land Texas Insurance Guide",
        "Richmond Texas Insurance Guide",
        "Galveston Texas Insurance Guide",
        "Katy Texas Insurance Guide",
        "Cypress Texas Insurance Guide",
        "Pearland Texas Insurance Guide",
        "The Woodlands Texas Insurance Guide",
        "Spring Texas Insurance Guide",
        "Conroe Texas Insurance Guide",
        "League City Texas Insurance Guide",
        "Baytown Texas Insurance Guide",
        "Pasadena Texas Insurance Guide",
        "Deer Park Texas Insurance Guide",
        "La Porte Texas Insurance Guide",
        "Friendswood Texas Insurance Guide",
        "Clear Lake Texas Insurance Guide",
        "Kingwood Texas Insurance Guide",
        "Humble Texas Insurance Guide",
        "Atascocita Texas Insurance Guide",
        "Channelview Texas Insurance Guide"
    ]
    
    topic = insurance_topics[int(time.time()) % len(insurance_topics)]
    
    # Generate blog content
    prompt = f"""
    Write a comprehensive, SEO-optimized blog post about "{topic}" for Inshora Group insurance.
    
    Write 4-5 detailed sections (H2) with 2-3 paragraphs each. Total 1500-1800 words.
    Include: intro with keyword, 4-5 main sections with full content, FAQ with 8-10 questions and detailed answers, conclusion with CTA.
    Mention Inshora Group 3-4 times naturally. Include "Call (713) 943-9985" and Texas cities.
    Use lead words: "Get a free quote," "Contact us," "Compare rates." Add urgency and social proof.
    
    CRITICAL: The content field MUST be a single markdown string with ALL sections combined, NOT separate fields.
    
    JSON format: title (60-70 chars), content (single markdown string with all sections), excerpt (150 chars), tags (8-10), meta_description (150 chars).
    """
    
    print(f"Generating blog post about: {topic}")
    
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an expert insurance writer and SEO specialist. Always respond with valid JSON format. Generate complete, comprehensive content without truncation. Write FULL paragraphs for each section, never cut off content."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=4000
    )
    
    blog_data = json.loads(response.choices[0].message.content)
    blog_data['author'] = 'Inshora AI'
    blog_data['category'] = 'Insurance Tips'
    
    # Generate image using DALL-E
    try:
        image_prompt = f"Professional insurance-related image about {topic}, modern business style, clean design, suitable for blog header"
        image_response = openai.images.generate(
            model="dall-e-3",
            prompt=image_prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        image_url = image_response.data[0].url
        print("✓ Image generated with DALL-E")
        
        # Try Cloudinary first (for production), fallback to local storage
        import requests
        import os
        from datetime import datetime
        
        from cloudinary_util import cloudinary_configured, configure_cloudinary

        cloudinary_available = cloudinary_configured()

        if cloudinary_available:
            try:
                import cloudinary.uploader

                configure_cloudinary()
                
                # Download and upload to Cloudinary
                img_response = requests.get(image_url, timeout=30)
                if img_response.status_code == 200:
                    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                    upload_result = cloudinary.uploader.upload(
                        img_response.content,
                        public_id=f"inshora_blog_{timestamp}",
                        folder="blog_images",
                        resource_type="image"
                    )
                    print(f"✓ Image uploaded to Cloudinary: {upload_result['public_id']}")
                    blog_data['image_url'] = upload_result['secure_url']
                else:
                    raise Exception(f"Failed to download image: {img_response.status_code}")
            except Exception as cloudinary_error:
                print(f"✗ Cloudinary upload failed, using local storage: {cloudinary_error}")
                cloudinary_available = False
        
        # Fallback to local storage (for development)
        if not cloudinary_available:
            # Create images directory if it doesn't exist
            images_dir = os.path.join(os.path.dirname(__file__), 'static', 'images')
            os.makedirs(images_dir, exist_ok=True)
            
            # Generate unique filename
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = f"blog_{timestamp}.png"
            filepath = os.path.join(images_dir, filename)
            
            # Download and save image locally
            img_response = requests.get(image_url, timeout=30)
            if img_response.status_code == 200:
                with open(filepath, 'wb') as f:
                    f.write(img_response.content)
                print(f"✓ Image saved locally: {filename}")
                blog_data['image_url'] = f"/static/images/{filename}"
            else:
                raise Exception(f"Failed to download image: {img_response.status_code}")
            
    except Exception as e:
        print(f"✗ Error generating/saving image: {e}")
        # Fallback to placeholder
        blog_data['image_url'] = 'https://via.placeholder.com/1200x630/0B1F8F/FFFFFF?text=Inshora+Insurance'
    
    blog_data['created_at'] = datetime.utcnow()
    blog_data['published'] = True
    
    return blog_data

def delete_expired_blog_posts(retention_days=None):
    """Remove blog posts older than retention_days (default 60). Runs on each daily job."""
    days = retention_days if retention_days is not None else BLOG_RETENTION_DAYS
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        result = blog_collection.delete_many({'created_at': {'$lt': cutoff}})
        deleted = result.deleted_count
        if deleted:
            logger.info(f"Deleted {deleted} blog post(s) older than {days} days (before {cutoff.isoformat()} UTC)")
            print(f"✓ Deleted {deleted} blog post(s) older than {days} days")
        else:
            logger.info(f"No blog posts older than {days} days to delete")
            print(f"✓ No blog posts older than {days} days to delete")
        return deleted
    except Exception as e:
        logger.error(f"Error deleting expired blog posts: {e}", exc_info=True)
        print(f"✗ Error deleting expired blog posts: {e}")
        return 0


def blog_already_exists(today_date):
    """Check if a blog post already exists for today"""
    try:
        # Start of day in Central timezone
        central_tz = pytz.timezone('America/Chicago')
        start_of_day = central_tz.localize(datetime.combine(today_date, datetime.min.time()))
        end_of_day = central_tz.localize(datetime.combine(today_date, datetime.max.time()))

        existing = blog_collection.find_one({
            'created_at': {
                '$gte': start_of_day,
                '$lte': end_of_day
            },
            'published': True
        })

        if existing:
            logger.info(f"Blog already exists for {today_date}: {existing.get('title', 'Unknown')}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error checking for existing blog: {e}", exc_info=True)
        return False

def save_blog_post(blog_data):
    """Save blog post to MongoDB"""
    try:
        result = blog_collection.insert_one(blog_data)
        logger.info(f"Blog post saved with ID: {result.inserted_id}")
        logger.info(f"Title: {blog_data['title']}")
        print(f"✓ Blog post saved with ID: {result.inserted_id}")
        print(f"  Title: {blog_data['title']}")
        return str(result.inserted_id)
    except Exception as e:
        logger.error(f"Error saving blog post: {e}", exc_info=True)
        print(f"✗ Error saving blog post: {e}")
        return None

def generate_and_publish_blog():
    """Main function to generate and publish a blog post with retry logic"""
    logger.info("=" * 60)
    logger.info("Starting automated blog generation")
    logger.info("=" * 60)
    
    print("=" * 60)
    print("Automated Blog Generation")
    print("=" * 60)
    print(f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print()
    
    # Check if job is already running (lock mechanism)
    if is_locked():
        logger.warning("Job already running (lock file exists). Skipping this run.")
        print("✗ Job already running (lock file exists). Skipping this run.")
        return False
    
    # Acquire lock
    if not acquire_lock():
        logger.error("Failed to acquire lock. Aborting job.")
        print("✗ Failed to acquire lock. Aborting job.")
        return False
    
    try:
        # Retention cleanup runs every day before publish attempt
        delete_expired_blog_posts()

        # Check for duplicate blog post for today
        central_tz = pytz.timezone('America/Chicago')
        today = datetime.now(central_tz).date()
        
        if blog_already_exists(today):
            logger.info(f"Blog already published for {today}. Skipping generation.")
            print(f"✓ Blog already published for {today}. Skipping generation.")
            
            # Log skipped run
            log_scheduler_run('skipped', attempts=0, error_message='Blog already exists for today')
            
            return True
        
        # Retry logic for transient failures with exponential backoff
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Exponential backoff: 30s, 60s, 120s
                if attempt > 0:
                    retry_delay = (2 ** attempt) * 30
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                
                logger.info(f"Attempt {attempt + 1}/{max_retries}")
                print(f"Attempt {attempt + 1}/{max_retries}")
                
                # Generate blog post
                logger.info("Generating blog post content...")
                blog_data = generate_blog_post()
                
                # Quality check: ensure blog content is not empty or too short
                if not blog_data:
                    raise Exception("No blog data generated")
                
                blog_content = blog_data.get('content', '')
                if not blog_content or len(blog_content) < 800:
                    raise Exception(f"Low quality blog generated: content length {len(blog_content)} < 800 characters")
                
                # Save to MongoDB
                logger.info("Saving blog post to database...")
                blog_id = save_blog_post(blog_data)
                
                if blog_id:
                    logger.info("Blog post generated and published successfully!")
                    print()
                    print("=" * 60)
                    print("✓ Blog post generated and published successfully!")
                    print("=" * 60)
                    
                    # Log successful run
                    log_scheduler_run('success', attempts=attempt + 1)
                    
                    # Send email notification
                    send_email_notification(blog_data)
                    
                    return True
                else:
                    logger.error(f"Failed to save blog post on attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying in {(2 ** (attempt + 1)) * 30} seconds...")
                        print(f"✗ Failed to save blog post. Retrying...")
                    else:
                        logger.error("Max retries reached. Failed to publish blog post.")
                        print()
                        print("=" * 60)
                        print("✗ Failed to publish blog post after max retries")
                        print("=" * 60)
                        
                        # Log failed run
                        log_scheduler_run('failed', attempts=max_retries, error_message='Max retries reached')
                        
                        return False
                    
            except Exception as e:
                logger.error(f"Error in blog generation (attempt {attempt + 1}): {e}", exc_info=True)
                print(f"✗ Error in blog generation (attempt {attempt + 1}): {e}")
                
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {(2 ** (attempt + 1)) * 30} seconds...")
                    print(f"Retrying...")
                else:
                    logger.error("Max retries reached. Failed to publish blog post.")
                    print()
                    print("=" * 60)
                    print("✗ Failed to publish blog post after max retries")
                    print("=" * 60)
                    import traceback
                    traceback.print_exc()
                    
                    # Log failed run with error details
                    log_scheduler_run('failed', attempts=max_retries, error_message=str(e))
                    
                    return False
        
        return False
        
    except Exception as e:
        logger.error(f"Unexpected error in blog generation: {e}", exc_info=True)
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        
        # Log failed run with error details
        log_scheduler_run('failed', attempts=0, error_message=f"Unexpected error: {str(e)}")
        
        return False
        
    finally:
        # Always release lock
        release_lock()

if __name__ == "__main__":
    # Check if running as cron job (single execution) or as scheduler daemon
    run_once = '--run-once' in sys.argv
    
    logger.info("=" * 60)
    logger.info("Starting Blog Scheduler")
    logger.info("=" * 60)
    
    if run_once:
        logger.info("Running in single-execution mode (cron job)")
        print("=" * 60)
        print("Blog Scheduler - Single Execution Mode")
        print("=" * 60)
        
        # Run once and exit
        success = generate_and_publish_blog()
        sys.exit(0 if success else 1)
    else:
        # Run as continuous scheduler daemon
        try:
            # Set up scheduler to run daily at 6 AM US Central Time
            scheduler = BackgroundScheduler(timezone=pytz.timezone('America/Chicago'))
            
            # Schedule job to run daily at 6:00 AM Central Time
            scheduler.add_job(
                generate_and_publish_blog,
                trigger=CronTrigger(hour=6, minute=0, timezone='America/Chicago'),
                id='daily_blog_post',
                name='Daily Blog Post Generation',
                replace_existing=True
            )
            
            logger.info("Scheduler configured to run daily at 6:00 AM America/Chicago")
            
            print("=" * 60)
            print("Blog Scheduler Started")
            print("=" * 60)
            print(f"Scheduler will run daily at 6:00 AM America/Chicago (US Central)")
            print(f"Current time (Central): {datetime.now(pytz.timezone('America/Chicago')).strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Log file: blog_scheduler.log")
            print(f"Lock file: {LOCK_FILE}")
            print(f"Success tracking: MongoDB scheduler_logs collection")
            print("=" * 60)
            print("\nFor cron job fallback, use:")
            print("0 6 * * * cd /path/to/backend && python blog_scheduler.py --run-once")
            print("=" * 60)
            
            # Start the scheduler
            scheduler.start()
            logger.info("Scheduler started successfully")
            
            try:
                # Keep the script running
                while True:
                    time.sleep(1)
            except (KeyboardInterrupt, SystemExit):
                # Shut down the scheduler gracefully
                logger.info("Shutting down scheduler...")
                scheduler.shutdown()
                logger.info("Scheduler shut down gracefully")
                print("\nScheduler shut down gracefully.")
                sys.exit(0)
                
        except Exception as e:
            logger.error(f"Fatal error starting scheduler: {e}", exc_info=True)
            print(f"✗ Fatal error starting scheduler: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
