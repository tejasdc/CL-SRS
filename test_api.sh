#!/bin/bash

# Test script for CL-SRS API

echo "Testing CL-SRS API..."
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# API URL
API_URL="http://localhost:8000"

# Test health endpoint
echo "1. Testing health endpoint..."
if curl -s "$API_URL/health" | grep -q "healthy"; then
    echo -e "${GREEN}✅ Health check passed${NC}"
else
    echo -e "${RED}❌ Health check failed${NC}"
    echo "Make sure the API server is running: python run_api.py"
    exit 1
fi

# Test ingest text
echo ""
echo "2. Testing text ingestion..."
RESPONSE=$(curl -s -X POST "$API_URL/ingest_text" \
    -H "Content-Type: application/json" \
    -d '{"text": "The Earth orbits around the Sun. It takes approximately 365.25 days to complete one orbit. This is why we have leap years every four years."}')

if echo "$RESPONSE" | grep -q "success"; then
    echo -e "${GREEN}✅ Text ingestion successful${NC}"
else
    echo -e "${RED}❌ Text ingestion failed${NC}"
    echo "Response: $RESPONSE"
fi

# Test author questions (this will fail without OpenAI API key)
echo ""
echo "3. Testing question generation..."
echo "(This requires OpenAI API key to be configured)"
RESPONSE=$(curl -s -X POST "$API_URL/author_questions" \
    -H "Content-Type: application/json" \
    -d '{"text": "The Earth orbits around the Sun. It takes approximately 365.25 days to complete one orbit."}')

if echo "$RESPONSE" | grep -q "concept_ids"; then
    echo -e "${GREEN}✅ Question generation successful${NC}"
elif echo "$RESPONSE" | grep -q "OPENAI_API_KEY"; then
    echo -e "${RED}❌ OpenAI API key not configured${NC}"
    echo "Please add your OpenAI API key to the .env file"
else
    echo -e "${RED}❌ Question generation failed${NC}"
    echo "Response: $RESPONSE"
fi

# Test due cards
echo ""
echo "4. Testing due cards endpoint..."
RESPONSE=$(curl -s "$API_URL/due_cards")

if echo "$RESPONSE" | grep -q "items"; then
    echo -e "${GREEN}✅ Due cards endpoint working${NC}"
else
    echo -e "${RED}❌ Due cards endpoint failed${NC}"
    echo "Response: $RESPONSE"
fi

echo ""
echo "API test complete!"