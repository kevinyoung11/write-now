import { config } from '../config/config';

export type TextGenMessage =
  | {
      command: 'finishTextGen';
      payload: {
        requestID: string;
        apiKey: string;
        result: string;
        prompt: string;
        detail: string;
      };
    }
  | {
      command: 'error';
      payload: {
        requestID: string;
        originalCommand: string;
        message: string;
      };
    };

/**
 * Use GPT API to generate text based on a given prompt
 * @param apiKey GPT API key
 * @param requestID Worker request ID
 * @param prompt Prompt to give to the GPT model
 * @param temperature Ignored for OpenAI Responses API GPT calls
 * @param stopSequences Ignored for OpenAI Responses API GPT calls
 * @param detail Extra string information to include (will be returned)
 * @param model OpenAI GPT model
 */
export type GptModel =
  | 'gpt-5.4'
  | 'gpt-5.4-pro'
  | 'gpt-5.4-mini'
  | 'gpt-5.4-nano'
  | 'gpt-5-mini'
  | 'gpt-5-nano'
  | 'gpt-5'
  | 'gpt-4.1';

export type TextGenProvider = 'openai' | 'gemini' | 'palm';

const textGenEndpoint = config.urls.textGenEndpoint;

export const textGenBackend = async (
  provider: TextGenProvider,
  apiKey: string,
  requestID: string,
  prompt: string,
  temperature: number,
  model: string,
  useCache: boolean = false,
  stopSequences: string[] = [],
  detail: string = '',
  cachePrefix: string = `[${provider}]`
) => {
  const cachedValue = localStorage.getItem(cachePrefix + prompt);
  if (useCache && cachedValue !== null) {
    console.log('Use cached output (text gen)');
    await new Promise(resolve => setTimeout(resolve, 1000));
    const message: TextGenMessage = {
      command: 'finishTextGen',
      payload: {
        requestID,
        apiKey,
        result: cachedValue,
        prompt,
        detail
      }
    };
    return message;
  }

  try {
    const response = await fetch(textGenEndpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        provider,
        request_id: requestID,
        prompt,
        temperature,
        model,
        stop_sequences: stopSequences,
        detail,
        api_key: apiKey
      })
    });
    const data = await response.json();
    if (response.status !== 200) {
      const detailMessage =
        typeof data?.detail === 'string' ? data.detail : JSON.stringify(data);
      throw Error(detailMessage);
    }

    const message = data as TextGenMessage;
    if (
      message.command === 'finishTextGen' &&
      useCache &&
      localStorage.getItem(cachePrefix + prompt) === null
    ) {
      localStorage.setItem(cachePrefix + prompt, message.payload.result);
    }
    return message;
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    const message: TextGenMessage = {
      command: 'error',
      payload: {
        requestID,
        originalCommand: 'startTextGen',
        message: errorMessage
      }
    };
    return message;
  }
};

export const textGenGpt = async (
  apiKey: string,
  requestID: string,
  prompt: string,
  temperature: number,
  model: GptModel,
  useCache: boolean = false,
  stopSequences: string[] = [],
  detail: string = ''
) => {
  if (stopSequences.length > 0) {
    console.warn(
      'Stop sequences are forwarded to the backend model proxy when supported.'
    );
  }
  return textGenBackend(
    'openai',
    apiKey,
    requestID,
    prompt,
    temperature,
    model,
    useCache,
    stopSequences,
    detail,
    '[gpt]'
  );
};
