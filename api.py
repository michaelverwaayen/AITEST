from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import uuid
import httpx
import os
import asyncio
import asyncpg
from fastapi.security import OAuth2PasswordBearer

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup OAuth2 password bearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

# ----------- MODELS -----------
class QueryRequest(BaseModel):
    query: str

class User(BaseModel):
    username: str

# ----------- DATABASE -----------
async def save_query_to_db(query: str, model_responses: dict, consensus_score: float, flagged: bool):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("""
        INSERT INTO queries (id, query, model_responses, consensus_score, flagged, timestamp)
        VALUES ($1, $2, $3, $4, $5, $6)
    """,
    str(uuid.uuid4()),
    query,
    model_responses,
    consensus_score,
    flagged,
    datetime.utcnow(),
    )
    await conn.close()

async def fetch_queries_from_db(flagged: bool = False):
    conn = await asyncpg.connect(DATABASE_URL)
    if flagged:
        rows = await conn.fetch("SELECT * FROM queries WHERE flagged = true ORDER BY timestamp DESC")
    else:
        rows = await conn.fetch("SELECT * FROM queries ORDER BY timestamp DESC")
    await conn.close()
    return [dict(row) for row in rows]

# ----------- HELPERS -----------
async def query_all_models(prompt: str):
    # Fake call – replace with actual model API requests
    return {
        "chatgpt": "42",
        "bard": "42",
        "copilot": "42",
        "deepseek": "41",
    }

def calculate_consensus(responses: dict):
    answers = list(responses.values())
    return 1.0 if len(set(answers)) == 1 else 0.5  # simplified

# ----------- AUTHENTICATION -----------
# Fake users database
fake_users_db = {
    "testuser": {
        "username": "testuser",
        "password": "testpassword",  # Should be hashed in production
    }
}

def fake_verify_token(token: str = Depends(oauth2_scheme)):  # Simulate token verification
    return fake_users_db.get("testuser")

# ----------- ROUTES -----------
@app.post("/query")
async def query_models(payload: QueryRequest, user: User = Depends(fake_verify_token)):  # Ensure authentication
    responses = await query_all_models(payload.query)
    consensus = calculate_consensus(responses)
    flagged = consensus < 1.0
    await save_query_to_db(payload.query, responses, consensus, flagged)
    return {
        "query": payload.query,
        "responses": responses,
        "consensus_score": consensus,
        "flagged": flagged,
    }

@app.get("/history")
async def get_history(flagged: bool = False, user: User = Depends(fake_verify_token)):  # Ensure authentication
    rows = await fetch_queries_from_db(flagged)
    return rows

# ----------- FRONTEND -----------
// React side: Get live data from Supabase
import { useEffect, useState } from "react";
import { Line } from "react-chartjs-2";
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend } from "chart.js";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

const Home = () => {
  const [dataPoints, setDataPoints] = useState([]);
  const [queryHistory, setQueryHistory] = useState([]);
  const [showFlaggedOnly, setShowFlaggedOnly] = useState(false);

  const fetchHistory = async (flaggedOnly = false) => {
    const res = await fetch(`http://localhost:8000/history?flagged=${flaggedOnly}`, {
      headers: {
        Authorization: `Bearer YOUR_TOKEN`,  // Pass your token here
      },
    });
    const data = await res.json();
    const points = data.map((d) => ({ x: new Date(d.timestamp).toLocaleDateString(), y: d.consensus_score }));
    setQueryHistory(data);
    setDataPoints(points);
  };

  useEffect(() => {
    fetchHistory(showFlaggedOnly);
  }, [showFlaggedOnly]);

  const chartData = {
    labels: dataPoints.map((point) => point.x),
    datasets: [
      {
        label: "Consensus Score",
        data: dataPoints.map((point) => point.y),
        fill: false,
        borderColor: "rgb(75, 192, 192)",
        tension: 0.1,
      },
    ],
  };

  return (
    <main>
      <h1>AI Auditing Dashboard</h1>
      <input
        type="checkbox"
        checked={showFlaggedOnly}
        onChange={() => setShowFlaggedOnly(!showFlaggedOnly)}
      />
      <h2>Consensus Score Over Time</h2>
      <Line data={chartData} />
      <table>
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Query</th>
            <th>Consensus</th>
            <th>Flagged</th>
          </tr>
        </thead>
        <tbody>
          {queryHistory.map((row) => (
            <tr key={row.id} className={row.flagged ? "bg-red-100" : ""}>
              <td>{new Date(row.timestamp).toLocaleString()}</td>
              <td>{row.query}</td>
              <td>{row.consensus_score}</td>
              <td>{row.flagged ? "Yes" : "No"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
};
