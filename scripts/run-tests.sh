#!/bin/bash
set -e

echo "🧪 Starting Meeting Automation Test Suite..."

# Backend
echo "--- Running Backend Tests ---"
cd backend
pytest tests/ -v --cov=app --cov-report=term-missing

# Frontend
echo "--- Running Frontend Tests ---"
cd ../frontend
npm test -- --watchAll=false --coverage

# Integration
echo "--- Running Integration Tests ---"
cd ../backend
pytest tests/integration/ -v

echo "✅ All tests completed successfully!"
