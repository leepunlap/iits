/**
 * Can this device talk to the UC-Mind board?
 *
 * The board is reached over Web Serial, which exists only in desktop Chrome/Edge (and ChromeOS).
 * iPads and phones are a hard no — Safari has no Web Serial at all — so the lab must SAY so up
 * front instead of showing a Connect button that can only fail.
 *
 * Pure function (takes the navigator, not the global one) so it can be unit-tested in Node with
 * fake user agents — the same "transport-injectable" trick lab.js uses for the board itself.
 */

export const PC_MAC_MESSAGE = '硬件連接需要 PC 或 Mac（用 Chrome／Edge，經 USB 線接主控板）';
export const PC_MAC_MESSAGE_EN = 'Connecting hardware needs a PC or Mac (Chrome/Edge, board on USB).';
export const BROWSER_MESSAGE = '呢個瀏覽器唔支援 Web Serial —— 請用 Chrome 或 Edge（PC／Mac）連接主控板';
export const BROWSER_MESSAGE_EN = 'This browser has no Web Serial — please use Chrome or Edge on a PC or Mac.';
export const SECURE_MESSAGE = '硬件連接需要 https 連線才可使用';
export const SECURE_MESSAGE_EN = 'Hardware needs a secure (https) connection.';

/** @returns {{ok:boolean, reason:string, message:string, message_en:string}} */
export function hwSupport(nav = typeof navigator === 'undefined' ? {} : navigator,
                          secure = typeof isSecureContext === 'undefined' ? true : !!isSecureContext) {
  const ua = String(nav.userAgent || '');
  // iPadOS 13+ reports itself as a Mac; the touch-point count is what gives it away.
  const ipad = /iPad|iPhone|iPod/.test(ua)
    || (nav.platform === 'MacIntel' && (nav.maxTouchPoints || 0) > 1)
    || (/Macintosh/.test(ua) && (nav.maxTouchPoints || 0) > 1);
  const android = /Android/.test(ua);
  const hasSerial = !!(nav.serial && typeof nav.serial.requestPort === 'function');

  if (hasSerial && secure) return { ok: true, reason: '', message: '', message_en: '' };
  if (ipad) return { ok: false, reason: 'ipad', message: PC_MAC_MESSAGE, message_en: PC_MAC_MESSAGE_EN };
  if (android) return { ok: false, reason: 'android', message: PC_MAC_MESSAGE, message_en: PC_MAC_MESSAGE_EN };
  if (!secure) return { ok: false, reason: 'insecure', message: SECURE_MESSAGE, message_en: SECURE_MESSAGE_EN };
  return { ok: false, reason: 'browser', message: BROWSER_MESSAGE, message_en: BROWSER_MESSAGE_EN };
}

/**
 * Show the verdict in the page: a notice the student can actually read, and (when unsupported)
 * a disabled Connect button instead of one that fails with a console error.
 * `connectSelector` is the button that must not be clickable on an unsupported device.
 */
export function applyHwNotice(support, doc = document, connectSelector = '#connect') {
  const banner = doc.createElement('div');
  banner.id = 'hwNotice';
  banner.className = 'hw-notice' + (support.ok ? ' ok' : ' bad');
  banner.setAttribute('role', 'status');
  banner.innerHTML = support.ok
    ? '<b>硬件可用</b>：<span>已偵測到 Web Serial，可以連接 UC-Mind 主控板。</span>'
    : '<b>硬件連接需要 PC 或 Mac</b>：<span>' + support.message + '</span>'
      + '<div class="en">' + support.message_en + '</div>';
  const host = doc.querySelector('main') || doc.body;
  const first = host.firstChild;
  if (first) host.insertBefore(banner, first); else host.appendChild(banner);

  if (!support.ok) {
    const btn = doc.querySelector(connectSelector);
    if (btn) {
      btn.disabled = true;
      btn.setAttribute('aria-disabled', 'true');
      btn.title = support.message;
    }
  }
  return support;
}
