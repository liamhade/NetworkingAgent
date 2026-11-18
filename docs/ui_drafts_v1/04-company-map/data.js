/* Sample data drawn from database/users/TEST_USER/searches/7258900d... (alignment text lightly trimmed). */
window.DATA = {
  title: 'Agentic AI and backend engineering roles',
  location: 'New York, NY',
  when: 'Nov 14, 3:45 PM',
  boards: 'Built In NYC, Lever, Ashby, Workable, Google',
  lookingFor: 'Software engineering roles, particularly in agentic AI, LLM applications, and backend or data infrastructure. Python or C++ oriented would be ideal.',
  summary: "You are targeting agentic AI, LLM application and backend roles in New York, with a preference for Python or C++. The strongest matches are Tracksuit's production AI agent role, Two Sigma's Python and C++ quant engineering roles, and Citadel's Python engineering roles. Alchemi, Palantir and Capital One have relevant AI roles, but they are less certain fits on seniority or posting detail.",
  companies: [
    { id: 'tracksuit', name: 'Tracksuit', url: 'https://www.builtinnyc.com/company/tracksuit', score: 82, searched: true,
      desc: 'Brand tracking platform that helps marketers prove their brand building is working, with offices in New York, London, Sydney and Auckland.',
      align: "You have shipped LLM tooling and MCP integrations at Dover, which matches Tracksuit's focus on production AI agents and MCP servers for go-to-market teams. Your work on a DSCSA-compliant pharmaceutical database also shows you can own production systems end to end.",
      jobs: [
        { id: 'j1', title: 'AI Engineer - GTM', url: '#', loc: 'New York, NY, USA', sal: '$162K-205K', score: 85,
          align: "You already build self-hosted LLM agents and custom MCPs, which maps directly to this role's agent and MCP server work. The posting asks for LLM work in production, and your Dover experience covers that." }
      ],
      people: [
        { id: 'p1', name: 'Keniel Yao', title: 'Head of Data Science', about: 'j1',
          align: 'As Head of Data Science, Keniel leads AI product work at Tracksuit, which is close to the LLM applications you build at Dover. A short conversation could help you understand how the team ships LLM products.',
          hook: "Tracksuit's production AI agent work caught my eye and I'd love to hear how your team ships LLM products." },
        { id: 'p2', name: 'River Vaughn Vink', title: 'Engineering Leader', about: 'j1',
          align: 'River is an engineering leader at Tracksuit, and the AI Engineer GTM role would sit within engineering, so River can describe the team and the hiring process.',
          hook: "I'm interested in the AI Engineer GTM role and would value your view of the engineering team." },
        { id: 'p3', name: 'Claire Li', title: 'GTM Engineer', about: 'j1',
          align: 'Claire works as a GTM Engineer at Tracksuit, which is the exact kind of role the AI Engineer GTM posting supports, so she can describe the day-to-day work.',
          hook: "I'm curious what day-to-day work looks like for GTM engineering at Tracksuit." },
        { id: 'p4', name: 'Trey Hodges', title: 'Engineering Manager', about: 'j1',
          align: 'Trey appeared in the search for AI engineering managers at Tracksuit and is a useful contact for how the AI team is organised.',
          hook: "I'd like to learn how Tracksuit organises its AI engineering team." }
      ] },
    { id: 'twosigma', name: 'Two Sigma', url: '#', score: 80, searched: true,
      desc: 'Quantitative investment management and trading firm that applies science, AI and data to investing.',
      align: "Your Python and C++ skills match Two Sigma's quant engineering stack, and your graph-based runtime optimization at Dover is close to the low-latency problems these teams work on.",
      jobs: [
        { id: 'j2', title: 'Quantitative Software Engineer: Fast Engineering', url: '#', loc: 'New York, NY, USA', sal: '$165K-300K', score: 80, align: 'Your C++ and Python work and your 2.3x runtime improvement fit the low-latency focus of this role.' },
        { id: 'j3', title: 'Quantitative Software Engineer: Generative AI', url: '#', loc: 'New York, NY, USA', sal: '$165K-300K', score: 78, align: 'This role combines LLM systems with financial data, which connects to your LLM and agent work at Dover.' },
        { id: 'j4', title: 'Software Engineer, Trading Engineering', url: '#', loc: 'New York, NY, USA', sal: '$165K-250K', score: 70, align: 'Building high-performance trading platforms draws on the performance optimization you did at Dover.' },
        { id: 'j5', title: 'Software Engineer', url: '#', loc: 'New York, NY, USA', sal: '$165K-325K', score: 68, align: 'This role covers distributed systems and infrastructure for research and analytics, which matches your backend background.' }
      ],
      people: [
        { id: 'p5', name: 'Ian Friedman', title: 'VP, Engineering Manager', about: 'j2', align: 'You are targeting the Fast Engineering role, and Ian is an engineering manager on that kind of team.', hook: "I'm applying for the Fast Engineering role and would value your perspective." },
        { id: 'p6', name: 'Jingbin Li', title: 'Quantitative Software Engineer', about: 'j2', align: 'Jingbin holds the Quantitative Software Engineer title you are targeting, so can speak directly about the work.', hook: "I'm a Python and C++ engineer interested in the quant engineering path." },
        { id: 'p7', name: 'Xiaofan Yang', title: 'Engineering Manager, Modeling Languages', about: 'j3', align: 'Xiaofan manages engineering on modeling languages, which is close to the research infrastructure you want to join.', hook: "Your modeling languages work is close to my interest in research infrastructure." },
        { id: 'p8', name: 'Joel Abraham', title: 'Quantitative Software Engineer', about: 'j2', align: 'Joel is a Quantitative Software Engineer based in New York, which matches your location and target role.', hook: "I'm also based in New York and exploring quant engineering." },
        { id: 'p9', name: 'Jesse Brizzi', title: 'Vice President, Software Engineer', about: 'j5', align: 'Jesse works in backend engineering and machine learning, which overlaps with your backend background.', hook: "Your backend and ML work overlaps with what I do at Dover." },
        { id: 'p10', name: 'Julian Woo', title: 'Software Engineer', about: 'j4', align: 'Julian is a recent CS graduate now at Two Sigma, so he can share how the move from university worked.', hook: "I studied CS at UChicago and would love to hear how you made the move." }
      ] },
    { id: 'citadel', name: 'Citadel', url: '#', score: 78, searched: false,
      desc: 'Investment firm with engineering teams that build platforms for research, trading and risk.',
      align: 'Your Python experience lines up with the Python engineering role, and your graduate background fits the university graduate posting.',
      jobs: [
        { id: 'j6', title: 'Software Engineer - University Graduate (US)', url: '#', loc: 'New York, NY, USA', sal: '$235K-300K', score: 84, align: 'This entry-level role builds research platforms with distributed computing and machine learning, which fits your background.' },
        { id: 'j7', title: 'Python Software Engineer', url: '#', loc: 'New York, NY, USA', sal: '$200K-3M', score: 80, align: 'This role focuses on Python services, APIs and tools, which is your strongest language.' }
      ], people: [] },
    { id: 'alchemi', name: 'Alchemi', url: '#', score: 75, searched: false,
      desc: 'Company with an open AI Engineer role posted on its Ashby careers page.',
      align: 'The AI Engineer role lines up with your LLM and agent experience at Dover. The posting gives few details, so you would need to learn more about the work.',
      jobs: [ { id: 'j8', title: 'AI Engineer', url: '#', loc: 'NYC preferred', sal: '', score: 76, align: 'This role is a direct match for your LLM and agent work, and the NYC preference fits your location.' } ],
      people: [] },
    { id: 'palantir', name: 'Palantir', url: '#', score: 74, searched: true,
      desc: 'Software company that builds data analysis and AI platforms for government and enterprise customers.',
      align: "Your work on agentic AI and LLM tooling matches Palantir's applied AI focus in New York. The internship posting is less senior than your current role.",
      jobs: [
        { id: 'j9', title: 'Software Engineer - Applied AI, Defense Applications', url: '#', loc: 'New York, NY', sal: '', score: 75, align: 'This applied AI role draws on the LLM and agent work you already do at Dover.' },
        { id: 'j10', title: 'Software Engineer, Internship - Sovereign AI Systems', url: '#', loc: 'New York, NY', sal: '', score: 70, align: 'This internship covers AI systems work close to your current projects, though you already work full time.' }
      ], people: [] },
    { id: 'capone', name: 'Capital One', url: '#', score: 60, searched: true,
      desc: 'Large bank and financial services company with AI platform teams in New York.',
      align: 'Your LLM and agent experience matches the AI platform work in these roles. The AI Engineer 4 title is a senior level, so weigh whether it fits.',
      jobs: [
        { id: 'j11', title: 'AI Engineer 4 (Gen AI Platform Services)', url: '#', loc: 'New York, NY, USA', sal: '$197K-246K', score: 60, align: 'This role covers LLM inference, agents and evaluation, which matches the production LLM systems you have built.' },
        { id: 'j12', title: 'AI Engineer 4 (AI Foundations)', url: '#', loc: 'New York, NY, USA', sal: '$197K-246K', score: 58, align: 'This role focuses on agentic workflows, guardrails and evaluation, which fit your agent work at Dover.' }
      ], people: [] }
  ],
  init: { pins: ['twosigma', 'p6'], applied: ['j7'], connected: ['p3'] }
};
