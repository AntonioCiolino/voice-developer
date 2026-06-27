#!/bin/bash
set -e

echo "🚀 voice-developer setup"
echo

# 1. Ensure .env exists
if [ ! -f controller/.env ]; then
    echo "⚠️  controller/.env not found"
    echo "Create it with your ANTHROPIC_API_KEY:"
    echo "  echo 'ANTHROPIC_API_KEY=sk-ant-...' > controller/.env"
    exit 1
fi

# 2. Create venv and install deps
echo "📦 Installing dependencies..."
cd controller
if [ ! -d venv ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt
cd ..

# 3. Test aider is available
echo "✓ Checking aider..."
AIDER_PATH=$(source controller/venv/bin/activate && which aider)
if [ -z "$AIDER_PATH" ]; then
    echo "❌ aider not found in venv. Try:"
    echo "  source controller/venv/bin/activate"
    echo "  pip install aider-chat"
    exit 1
fi
echo "  Found: $AIDER_PATH"

# 4. Test aider can call Claude
echo "✓ Testing aider with Claude..."
TEST_DIR=$(mktemp -d)
echo "export default function App() { return <div>test</div>; }" > "$TEST_DIR/App.jsx"
cd "$TEST_DIR"
export ANTHROPIC_API_KEY=$(grep ANTHROPIC_API_KEY ../../controller/.env | cut -d= -f2)
if ! timeout 30 aider --yes-always --no-pretty --model claude-sonnet-4-6 --message "respond with 'ok'" App.jsx > /dev/null 2>&1; then
    echo "❌ aider test failed. Check your ANTHROPIC_API_KEY"
    exit 1
fi
cd - > /dev/null
rm -rf "$TEST_DIR"
echo "  ✓ Claude API working"

echo
echo "✅ Setup complete!"
echo
echo "Next: run './start.sh' to start the controller + vite"
