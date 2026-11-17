/* Sample data, shaped like database/users/TEST_USER/searches/7258900d....json (companies > jobs, people). */
window.DATA = (function () {
  const search = {
    id: '7258900d1d3b416ebedf5c53cad61f0c',
    title: 'Software engineering roles, particularly in agentic AI, LLM applications and backend or data infrastructure',
    short: 'Software engineering roles, particularly in agentic AI',
    location: 'New York, NY',
    created: 'Yesterday, 3:45 PM',
    boards: ['Built In NYC', 'Lever', 'Ashby', 'Workable', 'Google'],
    summary: "You are targeting agentic AI, LLM application and backend roles in New York, with a preference for Python or C++. The strongest matches are Tracksuit's production AI agent role, Two Sigma's Python and C++ quant engineering roles, and Citadel's Python engineering roles. Alchemi, Palantir and Capital One have relevant AI roles, but they are less certain fits on seniority or posting detail."
  };

  const companies = [
    { key: 'company:name:tracksuit', name: 'Tracksuit', url: 'https://www.builtinnyc.com/company/tracksuit', score: 82, loc: 'New York, NY',
      description: 'Brand tracking platform that helps marketers prove their brand building is working, with offices in New York, London, Sydney and Auckland.',
      alignment: "You have shipped LLM tooling and MCP integrations at Dover, which matches Tracksuit's focus on production AI agents and MCP servers for go-to-market teams. Your work on a DSCSA-compliant pharmaceutical database also shows you can own production systems end to end.",
      keywords: ['AI engineering manager', 'go-to-market engineering lead'], searched: true },
    { key: 'company:name:two sigma', name: 'Two Sigma', url: 'https://www.builtinnyc.com/company/two-sigma', score: 80, loc: 'New York, NY',
      description: 'Systematic investment manager that applies technology, data science and engineering to financial markets, with a large engineering organisation in New York.',
      alignment: "Your Python and C++ background and your work on data-heavy backend systems line up with Two Sigma's quantitative engineering teams. The Generative AI role is the closest match to the LLM tooling you build at Dover, and four open roles give you several ways in.",
      keywords: ['engineering manager', 'quantitative software engineer'], searched: true },
    { key: 'company:name:citadel', name: 'Citadel', url: 'https://www.builtinnyc.com/company/citadel', score: 78, loc: 'New York, NY',
      description: 'Global multi-strategy investment firm with a large in-house engineering team building trading, risk and data systems.',
      alignment: "Citadel's Python engineering roles reward production backend experience like yours. The graduate programme is aimed at earlier-career candidates, so the Python Software Engineer role is the more realistic target.",
      keywords: ['Python engineering lead', 'software engineering recruiter'], searched: false },
    { key: 'company:name:alchemi', name: 'Alchemi', url: 'https://www.builtinnyc.com/company/alchemi', score: 75, loc: 'NYC preferred',
      description: 'Applied AI company building LLM-powered products; the posting lists New York as a preferred location.',
      alignment: "The AI Engineer role overlaps with your agentic chat interface work, but the posting says little about seniority or stack, so treat it as a possible fit and check the details before applying.",
      keywords: ['AI engineering lead', 'founding engineer'], searched: false },
    { key: 'company:name:palantir', name: 'Palantir', url: 'https://www.builtinnyc.com/company/palantir', score: 74, loc: 'New York, NY',
      description: 'Builds data integration and decision-making software for government and commercial customers.',
      alignment: "Applied AI roles at Palantir sit close to your LLM application work. The defense-focused posting may require clearance eligibility, and the internship is below your level, so only the first role is a realistic match.",
      keywords: ['forward deployed engineer', 'applied AI lead'], searched: false },
    { key: 'company:name:capital one', name: 'Capital One', url: 'https://www.builtinnyc.com/company/capital-one', score: 60, loc: 'New York, NY',
      description: 'Bank and technology company building cloud-native data and machine learning platforms.',
      alignment: "Both AI Engineer 4 roles touch Gen AI platform work you could credit, but they are a seniority stretch and focus on platform services rather than agents, so they rank lower.",
      keywords: ['Gen AI platform lead', 'AI foundations manager'], searched: false }
  ];

  const J = (key, co, title, loc, salary, score, alignment, id) => ({ key: 'job:url:' + key, company: co, title, location: loc, salary, score, alignment,
    url: 'https://www.builtinnyc.com/job/' + key });
  const jobs = [
    J('ai-engineer-gtm/12251267', 'Tracksuit', 'AI Engineer - GTM', 'New York, NY, USA', '$162K-205K', 85, 'You already build self-hosted LLM agents and custom MCPs, which maps directly to this role\'s agent and MCP server work. The posting asks for LLM work in production, and your Dover experience covers that.'),
    J('two-sigma/quant-fast-eng', 'Two Sigma', 'Quantitative Software Engineer: Fast Engineering', 'New York, NY, USA', '$165K-300K', 80, 'Fast Engineering is a Python and C++ role on performance-sensitive systems. Your C++ exposure and backend data work fit, though low-latency depth is not obvious from your background.'),
    J('two-sigma/quant-genai', 'Two Sigma', 'Quantitative Software Engineer: Generative AI', 'New York, NY, USA', '$165K-300K', 78, 'The closest Two Sigma match to your LLM work: building tools around generative models for quantitative researchers. Your agentic chat interface is directly relevant.'),
    J('two-sigma/swe-trading', 'Two Sigma', 'Software Engineer, Trading Engineering', 'New York, NY, USA', '$165K-250K', 70, 'Backend trading systems work where your production database and data pipeline experience transfers, but there is no LLM focus.'),
    J('two-sigma/software-engineer', 'Two Sigma', 'Software Engineer', 'New York, NY, USA', '$165K-325K', 68, 'A general engineering role across Two Sigma teams. Strong compensation, but the posting is broad so the team match is uncertain.'),
    J('citadel/university-grad', 'Citadel', 'Software Engineer - University Graduate (US)', 'New York, NY, USA', '$235K-300K', 84, 'Highest pay of the set, but this is a graduate programme and likely expects recent-graduate status. Confirm eligibility before investing time.'),
    J('citadel/python-swe', 'Citadel', 'Python Software Engineer', 'New York, NY, USA', '$200K-3M', 80, 'Python-first backend role. Your production Python systems and data work match; the wide salary band reflects bonus-heavy pay.'),
    J('alchemi/ai-engineer', 'Alchemi', 'AI Engineer', 'NYC preferred', '', 76, 'Overlaps with your agent and LLM application work. Little detail in the posting about stack or level.'),
    J('palantir/applied-ai-defense', 'Palantir', 'Software Engineer - Applied AI, Defense Applications', 'New York, NY', '', 75, 'Applied AI engineering on defense customers. LLM deployment experience is relevant; check clearance requirements.'),
    J('palantir/intern-sovereign', 'Palantir', 'Software Engineer, Internship - Sovereign AI Systems', 'New York, NY', '', 70, 'Internship track, so likely below your level. Listed because the Sovereign AI focus is on-topic.'),
    J('capital-one/ai-eng-genai', 'Capital One', 'AI Engineer 4 (Gen AI Platform Services)', 'New York, NY, USA', '$197K-246K', 60, 'Gen AI platform services work. Relevant to your LLM tooling but a seniority stretch.'),
    J('capital-one/ai-eng-foundations', 'Capital One', 'AI Engineer 4 (AI Foundations)', 'New York, NY, USA', '$197K-246K', 58, 'Foundational ML platform role with less agent focus than your target.')
  ];

  const P = (slug, co, name, title, why, hook, ask) => ({ key: 'person:linkedin:' + slug, company: co, name, title, profile_url: 'https://www.linkedin.com/in/' + slug,
    alignment: why, connect_message: 'Hi ' + name.split(' ')[0] + ", I'm a software engineer building an agentic chat interface with self-hosted LLMs and custom MCPs at Dover, " + hook + " I'd love to connect and " + ask });
  const people = [
    P('keniel-yao', 'Tracksuit', 'Keniel Yao', 'Head of Data Science', 'As Head of Data Science, Keniel leads AI product work at Tracksuit, which is close to the LLM applications you build at Dover. A short conversation could help you understand how the team ships LLM products.', "so Tracksuit's production AI agent work caught my eye.", 'hear how your team ships LLM products.'),
    P('river-vaughn-vink', 'Tracksuit', 'River Vaughn Vink', 'Engineering Leader', 'An engineering leader at Tracksuit who can speak to the AI Engineer - GTM role and the team behind it.', 'and the AI Engineer - GTM role at Tracksuit looks like a close match.', 'learn what the team is working on.'),
    P('claire-li', 'Tracksuit', 'Claire Li', 'GTM Engineer', 'A GTM Engineer is likely a peer of the role you are targeting, so she can describe the day-to-day work on MCP integrations.', "and Tracksuit's MCP work for go-to-market teams is exactly what I enjoy.", 'hear what the GTM engineering role looks like day to day.'),
    P('trey-hodges', 'Tracksuit', 'Trey Hodges', '', 'Role is not listed on the profile, but he is a current Tracksuit employee and may be able to point you to the right hiring contact.', 'and I am exploring roles at Tracksuit.', 'ask for a pointer to the right team.'),
    P('xiaofan-yang', 'Two Sigma', 'Xiaofan Yang', 'Engineering Manager, Modeling Languages', 'Manages a team building modeling languages, so he understands both the Python and C++ stack and the tooling side of Two Sigma.', "and Two Sigma's Python and C++ tooling is very close to what I want to work on.", 'learn how your team approaches modeling infrastructure.'),
    P('jingbin-li', 'Two Sigma', 'Jingbin Li', 'Quantitative Software Engineer', 'Holds the title of one of the roles you are targeting, so he can speak to what the work is really like.', "and I'm interested in Two Sigma's quantitative software engineering roles.", 'hear about your experience in the role.'),
    P('joel-abraham', 'Two Sigma', 'Joel Abraham', 'Quantitative Software Engineer', 'Another Quantitative Software Engineer, useful as a second perspective on the Fast Engineering and Generative AI teams.', 'and I am exploring the Generative AI quantitative engineering role.', 'compare notes on how the teams differ.'),
    P('john-zhang', 'Two Sigma', 'John Zhang', 'Engineering Manager', 'Engineering managers at Two Sigma make hiring decisions, so this is a direct route to the people who read applications.', "and Two Sigma's engineering roles are a strong match for my background.", 'hear what you look for in new engineers.'),
    P('yousef-amin', 'Two Sigma', 'Yousef Amin', 'Software Engineer', 'A software engineer on the general track who can describe how teams are matched during hiring.', 'and I am applying for the Software Engineer role at Two Sigma.', 'ask how team matching works.'),
    P('cheryl-lin', 'Two Sigma', 'Cheryl Lin', '', 'Title not listed, but the profile shows a current Two Sigma role. Lower priority than the engineers above.', 'and I am researching engineering teams at Two Sigma.', 'ask a quick question about the teams.'),
    P('clay-wang', 'Two Sigma', 'Clay Wang', 'Software Engineer', 'A peer-level engineer who can give an honest view of culture and the interview process.', 'and I am interviewing in the quantitative engineering space.', 'hear about the interview process.'),
    P('julian-woo', 'Two Sigma', 'Julian Woo', 'Software Engineer', 'Another peer-level engineer; a good low-pressure first contact.', 'and Two Sigma is high on my list.', 'hear what working there is like.'),
    P('ian-friedman', 'Two Sigma', 'Ian Friedman', 'VP, Engineering Manager', 'Senior leader in engineering. A thoughtful note could be valuable, but expect a lower reply rate.', "and I admire the engineering culture at Two Sigma.", 'follow your work on the engineering side.'),
    P('jesse-brizzi', 'Two Sigma', 'Jesse Brizzi', 'Vice President, Software Engineer', 'A senior individual contributor with deep technical context, useful for questions about the Fast Engineering stack.', 'and I work with Python and C++ in data-heavy systems.', 'ask about the Fast Engineering stack.')
  ];

  /* which job each person is most relevant to (drives the "Message X about Y" cross-links) */
  const about = {
    'person:linkedin:keniel-yao': 'job:url:ai-engineer-gtm/12251267', 'person:linkedin:river-vaughn-vink': 'job:url:ai-engineer-gtm/12251267',
    'person:linkedin:claire-li': 'job:url:ai-engineer-gtm/12251267', 'person:linkedin:trey-hodges': 'job:url:ai-engineer-gtm/12251267',
    'person:linkedin:xiaofan-yang': 'job:url:two-sigma/quant-fast-eng', 'person:linkedin:jingbin-li': 'job:url:two-sigma/quant-fast-eng',
    'person:linkedin:joel-abraham': 'job:url:two-sigma/quant-genai', 'person:linkedin:john-zhang': 'job:url:two-sigma/swe-trading',
    'person:linkedin:yousef-amin': 'job:url:two-sigma/software-engineer', 'person:linkedin:cheryl-lin': 'job:url:two-sigma/software-engineer',
    'person:linkedin:clay-wang': 'job:url:two-sigma/quant-genai', 'person:linkedin:julian-woo': 'job:url:two-sigma/quant-fast-eng',
    'person:linkedin:ian-friedman': 'job:url:two-sigma/swe-trading', 'person:linkedin:jesse-brizzi': 'job:url:two-sigma/quant-fast-eng'
  };

  return { search, companies, jobs, people, about,
    history: [
      { id: 'run1', title: 'Data platform and ML infrastructure roles, remote friendly', meta: 'Searching... step 3 of 5', status: 'running', href: 'running.html' },
      { id: '7258', title: search.short, meta: 'Yesterday · 6 co · 12 jobs · 14 people', status: 'done', href: 'results.html', current: true },
      { id: 'h3', title: 'Backend engineer, fintech and payments, NYC', meta: 'Nov 12 · 5 co · 9 jobs · 11 people', status: 'done', href: 'results.html' },
      { id: 'h4', title: 'ML infrastructure at climate-tech companies, Boston', meta: 'Nov 9 · Cancelled', status: 'cancelled', href: 'results.html' },
      { id: 'h5', title: 'Quant developer, Chicago and New York', meta: 'Nov 3 · Failed', status: 'error', href: 'results.html' }
    ],
    state: {
      pins: { 'company:name:tracksuit': 1, 'company:name:two sigma': 1, 'job:url:ai-engineer-gtm/12251267': 1, 'person:linkedin:ian-friedman': 1 },
      applied: { 'job:url:two-sigma/quant-genai': 1 },
      connected: { 'person:linkedin:keniel-yao': 1 }
    }
  };
})();
