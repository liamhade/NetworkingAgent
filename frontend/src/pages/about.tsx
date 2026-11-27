import { BrandMark } from '@/components/brand-mark'
import { PageHeader } from '@/components/page-header'
import { viewHash } from '@/utils/view'

/** About: a short overview, then FAQ answers as native disclosures (`<details>`). */
export function AboutPage() {
  return (
    <div className="wrap narrow about">
      <PageHeader
        title="About Enishi"
        subtitle="Find the people behind the job, not just the job."
      />

      <section className="card about-intro" aria-label="Overview">
        <BrandMark size={48} />
        <p>
          Enishi turns your job search into a list of people to meet. Tell it about your
          background and what you want next, and it finds companies that fit, the jobs open
          there, and the people worth messaging first, each with a note on why you would get
          along and an example connection message. Pin what you like, mark what you have
          applied to or who you have connected with, and keep it all in one place.
        </p>
      </section>

      <h2 className="about-h">Frequently asked questions</h2>
      <div className="faq">
        <details>
          <summary>How do I use this site?</summary>
          <ol>
            <li>
              On <a href={viewHash('search')}>Search</a>, upload your resume (optional) to fill
              in the form, or write your background and what you are looking for yourself.
            </li>
            <li>
              Choose the job boards to search under <b>Search boards</b>, then start the search.
              It takes a few minutes, and keeps going if you look at other tabs.
            </li>
            <li>
              Open a company on the results page to see its jobs and people. Use{' '}
              <b>Find more people</b> to search for more contacts; tick{' '}
              <b>Only people from my school</b> to look for fellow alumni.
            </li>
            <li>
              Pin companies, jobs and people, and mark jobs applied and people connected. The{' '}
              <a href={viewHash('companies')}>Companies</a>, <a href={viewHash('jobs')}>Jobs</a>{' '}
              and <a href={viewHash('people')}>People</a> tabs collect them across all your
              searches.
            </li>
          </ol>
        </details>

        <details>
          <summary>What does "enishi" mean?</summary>
          <p>
            <span lang="ja">縁</span> (<i>enishi</i>) is a Japanese word for the bond between
            people: the connection, or fate, that brings two people together. It is often
            pictured as a red thread tying them to each other. The logo is that thread joining
            two people, because a good job usually starts with the right person.
          </p>
        </details>

        <details>
          <summary>What do you do with my data?</summary>
          <ul>
            <li>
              <b>What is stored:</b> your account email, your latest resume and what was read
              from it, your searches and their results, saved search setups, pins, and which
              jobs and people you have marked. Only the latest resume is kept.
            </li>
            <li>
              <b>Who sees it:</b> you. Searches are tied to your account. The site owner can see
              who has an account and how much AI usage each account has, to keep costs in check.
            </li>
            <li>
              <b>What leaves the site:</b> to read your resume and plan and write up a search,
              your profile is sent to an AI model (Anthropic's Claude). Job and people searches
              go to job boards and Google with search terms such as role titles, company names
              and your school, never your resume itself.
            </li>
            <li>
              <b>What is never done:</b> your data is not sold or shared for advertising, and
              nothing is posted or sent on LinkedIn for you. Connection messages are only
              suggestions.
            </li>
            <li>
              <b>Removing it:</b> you can delete your saved resume on the Search page, and any
              search from the Previous searches list. To delete your account, ask the site
              owner.
            </li>
          </ul>
        </details>
      </div>
    </div>
  )
}
