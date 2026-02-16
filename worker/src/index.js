export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin') || '';
    const allowed = env.ALLOWED_ORIGIN || 'https://ndmacrocharts.com';

    // Also allow localhost for development
    const isAllowed = origin === allowed || origin.startsWith('http://localhost') || origin.startsWith('http://127.0.0.1');

    const corsHeaders = {
      'Access-Control-Allow-Origin': isAllowed ? origin : allowed,
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders });
    }

    if (request.method !== 'POST') {
      return new Response(JSON.stringify({ error: 'Method not allowed' }), {
        status: 405,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    try {
      const body = await request.json();
      const { messages, context } = body;

      if (!messages || !Array.isArray(messages) || messages.length === 0) {
        return new Response(JSON.stringify({ error: 'Messages required' }), {
          status: 400,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        });
      }

      // Build system prompt with chart context
      const systemPrompt = buildSystemPrompt(context);

      // Call Anthropic API
      const anthropicResp = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': env.ANTHROPIC_API_KEY,
          'anthropic-version': '2023-06-01',
        },
        body: JSON.stringify({
          model: 'claude-sonnet-4-5-20250929',
          max_tokens: 1024,
          system: systemPrompt,
          messages: messages.slice(-20), // Keep last 20 messages for context window
        }),
      });

      if (!anthropicResp.ok) {
        const errText = await anthropicResp.text();
        return new Response(JSON.stringify({ error: `Anthropic API error: ${anthropicResp.status}`, details: errText }), {
          status: 502,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        });
      }

      const result = await anthropicResp.json();
      const reply = result.content?.[0]?.text || 'No response generated.';

      return new Response(JSON.stringify({ reply }), {
        status: 200,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });

    } catch (err) {
      return new Response(JSON.stringify({ error: err.message }), {
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }
  },
};

function buildSystemPrompt(context) {
  let prompt = `You are an economics analyst assistant embedded in a macro data charting website (ndmacrocharts.com). The user is viewing an analysis page titled "AI Impact on Professional Services Employment."

THESIS BEING EXAMINED: AI is not killing professional services employment. Despite predictions of mass displacement of programmers, accountants, lawyers, consultants, and engineers, the data may tell a different story.

The page displays Bureau of Labor Statistics Current Employment Statistics (CES) data for these series (employment in thousands):

1. Total nonfarm (reference aggregate)
2. Professional and business services (PBS total)
3. Professional, scientific, and technical services
4. Computer systems design and related services
5. Custom computer programming services
6. Computer systems design services
7. Legal services
8. Accounting, tax preparation, bookkeeping, and payroll services
9. Management, scientific, and technical consulting services
10. Management consulting services
11. Architectural, engineering, and related services
12. Scientific research and development services
13. Software publishers
14. Specialized design services
15. Advertising, public relations, and related services
16. Information sector

Available views: Raw Data (absolute levels), YoY % Change, MoM Change, Trailing 3M Change, % of Total nonfarm.

The user can see these charts and may ask about trends, comparisons, or interpretations.`;

  if (context?.mode) {
    prompt += `\n\nThe user is currently viewing the "${context.mode}" mode.`;
  }
  if (context?.horizon) {
    prompt += ` Time horizon: ${context.horizon === 0 ? 'Max' : context.horizon + ' months'}.`;
  }

  if (context?.dataSummary) {
    prompt += `\n\nRecent data summary:\n${context.dataSummary}`;
  }

  prompt += `\n\nKeep responses concise and data-focused. Reference specific series and trends visible in the charts. When making claims, ground them in the data. If the user asks about data you don't have, suggest which view/page on the site might help.`;

  return prompt;
}
