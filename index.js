const express = require('express');
const axios = require('axios');

const app = express();
app.use(express.json());

async function askOllama(prompt) {
  const response = await axios.post('http://localhost:11434/api/generate', {
    model: 'qwen2.5-coder:1.5b',
    prompt: prompt,
    stream: false
  });
  return response.data.response;
}

app.post('/analyze', async (req, res) => {
  const { transcript } = req.body;
  const result = await askOllama(`Analysiere Meeting: ${transcript}`);
  res.json({ analysis: result });
});

app.listen(3000, () => console.log('API läuft auf Port 3000'));
