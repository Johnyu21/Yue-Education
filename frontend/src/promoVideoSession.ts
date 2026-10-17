// Fresh page load only: internal navigation does not reopen the video.
const initialPath=(window.location.hash.replace(/^#/,'')||'/').split('?')[0]
const previousScrollRestoration=window.history.scrollRestoration
const initialHome=initialPath==='/'
// Prevent the browser from restoring a scrolled position over the opening video.
if(initialHome)window.history.scrollRestoration='manual'
export const promoVideoSession={
 autoExpandPending:initialHome,
 restoreScroll(){if(initialHome)window.history.scrollRestoration=previousScrollRestoration}
}
