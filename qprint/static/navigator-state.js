// Keep browser navigation updates in order, including after a failed request.
export function createFocusPublisher(send, onError) {
  let pending = Promise.resolve();
  return payload => {
    const snapshot = {...payload};
    pending = pending.then(() => send(snapshot)).catch(onError);
    return pending;
  };
}

export function browserSession(search, storage, makeId) {
  const requested = new URLSearchParams(search).get('navigator_session');
  if (requested) return requested;
  const key = 'qprint.navigator.session';
  try {
    const store = typeof storage === 'function' ? storage() : storage;
    const existing = store.getItem(key);
    if (existing) return existing;
    const session = makeId();
    store.setItem(key, session);
    return session;
  } catch {
    return makeId();
  }
}
