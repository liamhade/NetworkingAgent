/* Sample data shaped like database/users/TEST_USER/searches/*.json (names of non-sample people are invented). */
window.NA = window.NA || {};
NA.SEARCH = {
  title: 'Software engineering roles, particularly in agentic AI, LLM applications and backend infrastructure',
  loc: 'New York, NY', date: 'Yesterday, 3:45 PM', looking: 'Python or C++', boards: 'Built In NYC, Lever, Ashby, Workable, Google',
  summary: "You are targeting agentic AI, LLM application and backend roles in New York, with a preference for Python or C++. The strongest matches are Tracksuit's production AI agent role, Two Sigma's Python and C++ quant engineering roles, and Citadel's Python engineering roles. Alchemi, Palantir and Capital One have relevant AI roles, but they are less certain fits on seniority or posting detail."
};
const li = n => 'https://www.linkedin.com/in/' + n;
NA.COMPANIES = [
  { name: 'Tracksuit', url: 'https://www.builtinnyc.com/company/tracksuit', score: 82, pinned: false,
    desc: 'Brand tracking platform that helps marketers prove their brand building is working.',
    alignment: "You have shipped LLM tooling and MCP integrations at Dover, which matches Tracksuit's focus on production AI agents and MCP servers for go-to-market teams. Your work on a DSCSA-compliant pharmaceutical database also shows you can own production systems end to end.",
    jobs: [
      { title: 'AI Engineer - GTM', loc: 'New York, NY', sal: '162K-205K', score: 85, pinned: true, url: 'https://www.builtinnyc.com/job/ai-engineer-gtm/12251267',
        alignment: "You already build self-hosted LLM agents and custom MCPs, which maps directly to this role's agent and MCP server work. The posting asks for LLM work in production, and your Dover experience covers that." },
      { title: 'Senior Software Engineer, Platform', loc: 'New York, NY', sal: '150K-190K', score: 71,
        alignment: 'Backend platform work in Python lines up with your data infrastructure background, though the posting leans toward seniority you may be a stretch for.' }
    ],
    people: [
      { name: 'Keniel Yao', title: 'Head of Data Science', done: true, follow: false, url: li('keniel-yao'),
        alignment: 'As Head of Data Science, Keniel leads AI product work at Tracksuit, which is close to the LLM applications you build at Dover. A short conversation could help you understand how the team ships LLM products.',
        msg: "Hi Keniel, I'm a software engineer building an agentic chat interface with self-hosted LLMs and custom MCPs at Dover, so Tracksuit's production AI agent work caught my eye. I'd love to connect and hear how your team ships LLM products." },
      { name: 'Maya Patel', title: 'Engineering Manager, AI', url: li('maya-patel'),
        alignment: 'Maya manages the engineers behind the AI Engineer - GTM opening, so she is the most direct route to that role.',
        msg: "Hi Maya, I saw Tracksuit is hiring an AI Engineer for GTM. I build agentic tools with MCP at Dover and would love to connect and learn how your team works." }
    ],
    more: [{ name: 'Ollie Grant', title: 'Staff Engineer, Agents', url: li('ollie-grant'), alignment: 'Ollie works on the agent runtime, which overlaps with your self-hosted LLM work.', msg: 'Hi Ollie, I build self-hosted LLM agents at Dover and admire what Tracksuit is shipping. Would love to connect.' }] },
  { name: 'Two Sigma', url: 'https://www.builtinnyc.com/company/two-sigma', score: 78, pinned: true,
    desc: 'Systematic investment manager applying data science and engineering to financial markets.',
    alignment: 'Two Sigma hires Python and C++ engineers for quant platform work. Your backend and data-pipeline experience transfers well, although finance domain knowledge would be new.',
    jobs: [
      { title: 'Quantitative Software Engineer, Python', loc: 'New York, NY', sal: '175K-250K', score: 80, done: true, url: '#',
        alignment: 'Python-first quant tooling is a direct match for your stack, and the posting values clean data infrastructure.' },
      { title: 'Software Engineer, C++ Trading Infrastructure', loc: 'New York, NY', sal: '190K-260K', score: 77, url: '#',
        alignment: 'You list C++ as a preference. This role is low-latency heavy, so expect a steeper ramp, but the fit on systems thinking is solid.' },
      { title: 'Data Platform Engineer', loc: 'New York, NY', sal: '', score: 72, url: '#',
        alignment: 'Building internal data platforms resembles your DSCSA database work. Salary is not listed in the posting.' }
    ],
    people: [
      { name: 'Priya Raman', title: 'Managing Director, Engineering', pinned: true, url: li('priya-raman'),
        alignment: 'Priya leads the platform engineering group that owns two of these openings, so a note to her is high value.',
        msg: "Hi Priya, I'm a Python engineer building LLM infrastructure at Dover and I'm very interested in Two Sigma's platform engineering work. I'd love to connect." },
      { name: 'Marcus Lee', title: 'Software Engineer, Quant Platform', done: true, follow: true, url: li('marcus-lee'),
        alignment: 'Marcus sits on the team hiring for the Python quant role and can speak to day-to-day work.',
        msg: "Hi Marcus, I'm applying for the Quant Software Engineer role and would value hearing what the team's day-to-day looks like. Happy to connect." },
      { name: 'Hannah Cole', title: 'Technical Recruiter', url: li('hannah-cole'),
        alignment: 'Hannah recruits for engineering roles in New York and can confirm timelines and level.',
        msg: "Hi Hannah, I'm a software engineer interested in Python roles at Two Sigma. I'd appreciate connecting so I can follow your openings." },
      { name: 'Tomas Weiss', title: 'Head of Data Infrastructure', url: li('tomas-weiss'),
        alignment: 'Tomas heads the data infrastructure team behind the Data Platform Engineer role.',
        msg: "Hi Tomas, I build data pipelines and LLM tooling at Dover and your team's data platform work looks fascinating. I'd love to connect." }
    ],
    more: [{ name: 'Alicia Moreno', title: 'Engineering Manager, Research Platform', url: li('alicia-moreno'), alignment: 'Alicia manages a research platform team that uses Python heavily.', msg: 'Hi Alicia, I work on Python data infrastructure at Dover and would love to connect and learn about Two Sigma research platform.' }] },
  { name: 'Citadel', url: 'https://www.builtinnyc.com/company/citadel', score: 74, pinned: false,
    desc: 'Global investment firm with large engineering teams across trading and research.',
    alignment: 'Citadel posts Python engineering roles across trading systems. Your backend experience fits, but the postings are light on detail so fit is less certain.',
    jobs: [
      { title: 'Python Software Engineer, Trading Systems', loc: 'New York, NY', sal: '180K-240K', score: 74, pinned: true, url: '#',
        alignment: 'Python backend work for trading systems matches your preference. Detail is thin, so confirm scope when you connect.' }
    ],
    people: [
      { name: 'Elena Vasquez', title: 'Engineering Lead, Trading Technology', url: li('elena-vasquez'),
        alignment: 'Elena leads a Python-heavy trading technology team and is the right level to ask about the opening.',
        msg: "Hi Elena, I'm a Python engineer interested in Citadel's trading systems work. I'd love to connect and learn more about your team." },
      { name: 'Sam Brooks', title: 'Experienced Hire Recruiting', url: li('sam-brooks'),
        alignment: 'Sam handles experienced engineering hires in New York.',
        msg: "Hi Sam, I'm a software engineer exploring Python roles at Citadel and would appreciate connecting." }
    ], more: [] },
  { name: 'Alchemi', url: 'https://www.builtinnyc.com/company/alchemi', score: 68, pinned: false,
    desc: 'Early-stage startup building LLM applications for enterprise workflows.',
    alignment: 'A small AI startup where you would own a lot. Seniority and funding are less clear from the posting.',
    jobs: [{ title: 'ML Engineer, LLM Applications', loc: 'New York, NY', sal: '', score: 66, url: '#', alignment: 'LLM application work matches your Dover agent project, but the posting does not list stack or level.' }],
    people: [{ name: 'Jordan Kim', title: 'Co-founder and CTO', url: li('jordan-kim'), alignment: 'At a small startup the CTO is the hiring manager, so a direct note is the best route.', msg: "Hi Jordan, I build self-hosted LLM agents at Dover and Alchemi's applications caught my eye. I'd love to connect." }],
    more: [{ name: 'Rosa Alvarez', title: 'Founding Engineer', url: li('rosa-alvarez'), alignment: 'Rosa is an early engineer who can describe the stack first-hand.', msg: 'Hi Rosa, I work on LLM agents at Dover and would love to hear how Alchemi builds. Happy to connect.' }] },
  { name: 'Palantir', url: 'https://www.builtinnyc.com/company/palantir', score: 64, pinned: false,
    desc: 'Software company building data integration and AI platforms for government and enterprise.',
    alignment: 'Palantir has AI-focused engineering roles, but forward-deployed work involves travel and client-facing duty you did not mention wanting.',
    jobs: [{ title: 'Forward Deployed Software Engineer, AI', loc: 'New York, NY', sal: '140K-220K', score: 64, url: '#', alignment: 'Strong AI platform exposure, with a client-facing side that may not suit a backend preference.' }],
    people: [{ name: 'Ravi Shah', title: 'Engineering Manager, AIP', url: li('ravi-shah'), alignment: 'Ravi manages AI platform engineers and can explain what the role involves.', msg: "Hi Ravi, I build LLM agents at Dover and I'm curious about engineering on Palantir's AI platform. I'd love to connect." }],
    more: [] },
  { name: 'Capital One', url: 'https://www.builtinnyc.com/company/capital-one', score: 60, pinned: false,
    desc: 'Bank and technology company with a large machine-learning and cloud engineering organisation.',
    alignment: 'Capital One runs sizeable ML and agentic initiatives. Roles tend to be senior, so level is the open question.',
    jobs: [{ title: 'Senior ML Engineer, Agentic Systems', loc: 'New York, NY', sal: '165K-210K', score: 60, url: '#', alignment: 'Agentic systems is on target for you. The Senior title may be a stretch for your current level.' }],
    people: [{ name: 'Lauren Mitchell', title: 'Director, ML Engineering', url: li('lauren-mitchell'), alignment: 'Lauren directs the ML engineering org and posts about agent projects publicly.', msg: 'Hi Lauren, I build agentic chat tools with self-hosted LLMs and was interested in your posts on agent engineering at Capital One. I would love to connect.' }],
    more: [] }
];
