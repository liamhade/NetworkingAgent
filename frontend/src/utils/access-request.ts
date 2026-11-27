export const ACCESS_REQUEST_SUBJECT = 'Enishi access request'

/** The email someone sends the owner, from `email`, so the owner knows the address is theirs. */
export function accessRequestBody(email: string): string {
  return (
    `Hi,\n\nPlease approve ${email} for Enishi. I'm sending this from that ` +
    `address so you can confirm it's mine.\n\nThanks!`
  )
}

/** `mailto:` link that opens the request email, filled in, in the person's mail app. */
export function accessRequestMailto(to: string, email: string): string {
  const query = `subject=${encodeURIComponent(ACCESS_REQUEST_SUBJECT)}&body=${encodeURIComponent(accessRequestBody(email))}`
  return `mailto:${to}?${query}`
}
