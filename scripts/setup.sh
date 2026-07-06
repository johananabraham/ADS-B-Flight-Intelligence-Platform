#!/bin/bash
# ADS-B Flight Intelligence Platform - Setup Script

set -e

echo "🛫 ADS-B Flight Intelligence Platform Setup"
echo "============================================"

# Check for required tools
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo "❌ $1 is required but not installed."
        exit 1
    fi
    echo "✅ $1 found"
}

echo ""
echo "Checking dependencies..."
check_command python3
check_command node
check_command npm
check_command psql

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your database credentials and API keys"
fi

# Set up backend
echo ""
echo "Setting up backend..."
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
cd ..

# Set up frontend
echo ""
echo "Setting up frontend..."
cd frontend
npm install
cd ..

echo ""
echo "============================================"
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env with your configuration"
echo "2. Create the database:"
echo "   createdb adsb_intel"
echo "   psql adsb_intel -c 'CREATE EXTENSION postgis;'"
echo ""
echo "3. Install dump1090 and connect your RTL-SDR dongle"
echo "4. Start dump1090:"
echo "   dump1090 --net --interactive"
echo ""
echo "5. Start the services (in separate terminals):"
echo "   cd backend && source venv/bin/activate && uvicorn app.main:app --reload"
echo "   cd services/ingestion && python ingest.py"
echo "   cd frontend && npm run dev"
echo ""
echo "Or use Docker:"
echo "   docker-compose up -d"
echo ""
