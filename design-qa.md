# Snack hybrid redesign QA

final result: passed

## Target and evidence

- Selected target: option 2's alternating chat bubbles/composer combined with option 3's single dashboard sidebar. Combined source: `artifacts/redesign-hybrid-reference.png`.
- Source pixels: 1487 × 1058. Normalized to 1440 × 1024 for comparison (less than 0.02% aspect-ratio difference).
- Implementation: `artifacts/redesign-implementation-light.png`, 1440 × 1024; CSS viewport 1440 × 1024; deviceScaleFactor 1.
- State: light desktop, general channel, four screenshot-only messages matching the source copy and sender positions. Visual fixtures intercept history/bootstrap and isolate socket events; they do not modify stored messages. Functional tests run separately against real Django APIs/WebSockets.
- Full-view, side-by-side evidence: `artifacts/redesign-full-comparison-final.png` (source left, implementation right).
- Focused comparisons: `artifacts/redesign-sidebar-comparison-final.png` and `artifacts/redesign-chat-comparison-final.png`. These cover typography, icon placement, bubble/attachment geometry, and sidebar control shapes at readable scale.
- Additional captures: `artifacts/redesign-implementation-dark.png`, `artifacts/redesign-implementation-mobile.png` (390 × 844), `artifacts/redesign-login-light.png`, and `artifacts/redesign-dialog-dark.png`.

## Comparison history

### Pass 1 — blocked

Evidence: `artifacts/redesign-comparison-pass-1.png` and `artifacts/redesign-sidebar-comparison-pass-1.png`.

1. [P2] Message/sidebar typography was too small for the selected direction. Increased desktop body to 17px, sender names to 16px, avatars to 52px, channel names to 16px, and display weights to 800 using the supplied IRANYekanX fonts.
2. [P2] Invisible message actions reserved vertical space and clipped the fourth fixture bubble. Desktop actions now overlay on hover/focus; mobile actions remain visible in normal flow. Reduced redundant date/message spacing; a browser assertion now checks that the complete reference conversation fits above the composer.
3. [P2] Attachments looked like tiny inline links. Added the existing Lucide file icon, readable filename/size grouping, a separate download affordance, and a rounded outlined file tile.
4. [P2] Workspace/channel/profile row order differed from the chosen sidebar. These rows now isolate LTR icon/name ordering while channel text uses automatic direction and the product navigation stays Persian RTL.

### Pass 2 and production verification — passed

Evidence: `artifacts/redesign-full-comparison-final.png`, `artifacts/redesign-sidebar-comparison-final.png`, and `artifacts/redesign-chat-comparison-final.png`, captured from the production build.

The previous issues are resolved. All four fixture bubbles fit, ownership alternates correctly, the sidebar is unified, and persistent controls remain reachable. No actionable P0/P1/P2 findings remain.

## Required fidelity surfaces

- **Fonts/typography:** Actual IRANYekanXFaNum faces are loaded; real Regular through ExtraBold weights are retained. Desktop chat uses 17px/1.65 line-height, mobile 13px/1.8, with stronger rounded headings and 800-weight labels. Long names/attachments wrap. Account screens use the same font and tactile controls.
- **Spacing/layout:** The separate rail is removed. The right sidebar is 340px at 1440px, 295px on intermediate widths; mobile uses a dismissible right drawer. The source's 362px normalized sidebar is slightly narrowed to preserve practical chat space. Bubble radii, soft surfaces, thick outlines, raised primary buttons, and the compact composer follow the selected hybrid. Date/time metadata and product controls account for minor intentional density differences.
- **Colors/tokens:** Purple #6561d9, navy #252f47, white, lavender, and existing pastel avatar families remain. Dark surfaces and text use the existing dark palette. The selected purple is slightly deepened to #5651bb for readable text on lavender; muted light-theme text is #68748a (4.72:1 on white). No Duolingo green recoloring or fake gamification was added.
- **Asset fidelity:** This target contains UI controls and account initials, with no new raster illustration slots. Real Lucide components supply all icons, including file/download/send controls. The favicon is rendered from the same package's Asterisk icon. No handcrafted illustration substitutes or decorative emoji icons were introduced; message emoji remain user content. Initial colors derive from real account IDs and may differ from the mock's sample colors.
- **Copy/content:** Persian UI labels remain coherent and RTL. Real channel descriptions, names, dates, file sizes, and message content are dynamic. Timestamps, unread/all-conversation shortcuts, member management, workspace creation, and explicit logout are preserved rather than replacing them with nonfunctional mock-only controls or an invented online indicator.

## Interaction and responsive verification

Passed against the real local app:

- Two-user send/receive, edit/delete, reply, file upload, search, reconnect recovery, private-channel isolation, DM, refresh persistence, and mobile drawer navigation (`scripts/browser_smoke.py`).
- Signup, workspace onboarding, invitations through signup/acceptance, member permissions, final-admin guard, logout, invalid login, reset request, and safe login redirects (`scripts/browser_accounts.py`).
- Lucide icon rendering/accessible control names, formatting, emoji dialog, light/dark theme switching and navigation (`scripts/browser_icons.py`).
- Saved/system theme selection, reload/navigation persistence, keyboard toggle, and blocked storage (`scripts/browser_theme.py`).
- Visual fixture ownership/ordering, actual font loading, complete desktop conversation visibility, no horizontal overflow or clipped composer at 1024×768, 768×1024, 720×900, 390×844, and 320×740 (`scripts/browser_redesign.py`).
- Mobile drawer close button, outside-click dismissal, Escape dismissal and focus return; visible focus outlines and reduced-motion styling. No console errors or JavaScript exceptions in the final visual browser run.
- Production Next.js build and `git diff --check` passed. No backend code changed.

## Implementation checklist

- [x] Combine selected sidebar and chat layouts in the existing production app.
- [x] Preserve API/session/socket/upload behavior and existing controls.
- [x] Apply consistent controls to login/onboarding/dialogs and both themes.
- [x] Fix comparison findings and recapture the production build.
- [x] Verify desktop, tablet, and mobile layouts and interactions.

## Follow-up polish / limits

No P3 issue blocks this design handoff. Testing used installed Chrome; Safari/Firefox and physical mobile hardware were not checked. Docker deployment and real SMTP were not retested. The app remains local and was not deployed or committed in this redesign pass.
