const API = {
  // biome-ignore lint/suspicious/noExplicitAny: api impl
  get: async <T = any>(path: string): Promise<T> => {
    const response = await fetch(`/api${path}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch ${path} (${response.status})`);
    }
    return await response.json() as T;
  },
  // biome-ignore lint/suspicious/noExplicitAny: api impl
  post: async <T = any>(path: string, data: object) => {
    const url = `/api${path}`;
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      throw new Error(`Failed to fetch ${path} (${response.status})`);
    }

    return await response.json() as T;
  },
};

export default API;
