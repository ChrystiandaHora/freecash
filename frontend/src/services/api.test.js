import { beforeEach, describe, expect, it, vi } from 'vitest';

const { post } = vi.hoisted(() => ({ post: vi.fn() }));

vi.mock('axios', () => ({
  default: {
    post,
    create: () => ({
      interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } },
    }),
  },
}));

const { renovarAccessToken } = await import('./api');

beforeEach(() => {
  post.mockReset();
});

describe('renovarAccessToken', () => {
  it('devolve o access token novo emitido pelo refresh', async () => {
    post.mockResolvedValue({ data: { access: 'novo' } });

    await expect(renovarAccessToken()).resolves.toBe('novo');
    expect(post).toHaveBeenCalledWith(
      expect.stringContaining('/api/token/refresh/'),
      {},
      { withCredentials: true }
    );
  });

  it('compartilha uma renovação em andamento em vez de gastar o refresh duas vezes', async () => {
    post.mockResolvedValue({ data: { access: 'novo' } });

    const [primeiro, segundo] = await Promise.all([renovarAccessToken(), renovarAccessToken()]);

    expect(post).toHaveBeenCalledTimes(1);
    expect(primeiro).toBe('novo');
    expect(segundo).toBe('novo');
  });

  it('libera nova renovação depois que a anterior falha', async () => {
    post.mockRejectedValueOnce(new Error('refresh expirado'));
    post.mockResolvedValueOnce({ data: { access: 'depois' } });

    await expect(renovarAccessToken()).rejects.toThrow('refresh expirado');
    await expect(renovarAccessToken()).resolves.toBe('depois');
    expect(post).toHaveBeenCalledTimes(2);
  });
});
