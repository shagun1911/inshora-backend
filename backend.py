"""
Backend: creates a LiveKit room and dispatches the pre-running agent worker into it.
Also handles automated blog system with OpenAI and MongoDB.
"""
import os
import asyncio
import time
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from livekit import api
from dotenv import load_dotenv
from pymongo import MongoClient
import openai

load_dotenv()

app = Flask(__name__)
CORS(app)

LIVEKIT_URL = os.getenv("LIVEKIT_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")
ROOM_PREFIX = "inshora-sarah-x7k9-"

# MongoDB setup
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
client = MongoClient(MONGODB_URI)
db = client.inshora
blog_collection = db.blog_posts

# OpenAI setup
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route('/create_room', methods=['POST'])
def create_room():
    try:
        data = request.json or {}
        user_identity = data.get('identity', f'inshora-user-{os.urandom(4).hex()}')
        room_name = f"{ROOM_PREFIX}{int(time.time())}-{os.urandom(2).hex()}"
        result = asyncio.run(_create_room_async(room_name, user_identity))
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


async def _create_room_async(room_name, user_identity):
    lkapi = api.LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    try:
        await lkapi.room.create_room(api.CreateRoomRequest(
            name=room_name,
            empty_timeout=120,
        ))
        print(f"✓ Room created: {room_name}")

        # Dispatch the pre-running agent worker — no subprocess cold-start
        await lkapi.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name="inshora-sarah",
                room=room_name,
            )
        )
        print(f"✓ Agent dispatched for room: {room_name}")

        token = api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET) \
            .with_identity(user_identity) \
            .with_name(f"User {user_identity}") \
            .with_grants(api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
            ))

        return {
            'success': True,
            'room': room_name,
            'token': token.to_jwt(),
            'url': LIVEKIT_URL,
            'identity': user_identity,
        }
    finally:
        await lkapi.aclose()


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

# Blog API endpoints
@app.route('/api/blog', methods=['GET'])
def get_blogs():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        skip = (page - 1) * per_page
        
        blogs = list(blog_collection.find().sort('created_at', -1).skip(skip).limit(per_page))
        total = blog_collection.count_documents({})
        
        # Convert ObjectId to string
        for blog in blogs:
            blog['_id'] = str(blog['_id'])
        
        return jsonify({
            'success': True,
            'blogs': blogs,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/blog/<blog_id>', methods=['GET'])
def get_blog(blog_id):
    try:
        from bson.objectid import ObjectId
        blog = blog_collection.find_one({'_id': ObjectId(blog_id)})
        if blog:
            blog['_id'] = str(blog['_id'])
            return jsonify({'success': True, 'blog': blog})
        else:
            return jsonify({'success': False, 'error': 'Blog not found'}), 404
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/blog/generate', methods=['POST'])
def generate_blog():
    try:
        # Generate blog post using OpenAI
        blog_content = generate_blog_post()
        
        # Save to MongoDB
        blog_content['created_at'] = datetime.utcnow()
        result = blog_collection.insert_one(blog_content)
        
        return jsonify({
            'success': True,
            'blog_id': str(result.inserted_id),
            'message': 'Blog post generated successfully'
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

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
    Include: intro with keyword, 4-5 main sections with full content, FAQ with 3-4 questions, conclusion with CTA.
    Mention Inshora Group 3-4 times naturally. Include "Call (713) 943-9985" and Texas cities.
    Use lead words: "Get a free quote," "Contact us," "Compare rates." Add urgency and social proof.
    
    CRITICAL: The content field MUST be a single markdown string with ALL sections combined, NOT separate fields.
    
    JSON format: title (60-70 chars), content (single markdown string with all sections), excerpt (150 chars), tags (8-10), meta_description (150 chars).
    """
    
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an expert insurance writer and SEO specialist. Always respond with valid JSON format. Generate complete, comprehensive content without truncation. Write FULL paragraphs for each section, never cut off content."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=4000
    )
    
    import json
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
        blog_data['image_url'] = image_response.data[0].url
    except Exception as e:
        print(f"Error generating image with DALL-E: {e}")
        blog_data['image_url'] = 'https://via.placeholder.com/1200x630/0B1F8F/FFFFFF?text=Inshora+Insurance'
    
    return blog_data


if __name__ == '__main__':
    print("=" * 60)
    print("LiveKit Backend Server")
    print("=" * 60)
    print(f"Server running on: http://localhost:5001")
    print(f"LiveKit URL: {LIVEKIT_URL}")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5001, debug=False)
