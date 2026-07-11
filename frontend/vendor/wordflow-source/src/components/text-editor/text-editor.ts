import DiffMatchPatch from 'diff-match-patch';
import { css, html, LitElement, PropertyValues, unsafeCSS } from 'lit';
import { customElement, property, query, state } from 'lit/decorators.js';
import { unsafeHTML } from 'lit/directives/unsafe-html.js';
import { config } from '../../config/config';
import { textGenGemini } from '../../llms/gemini';
import { textGenGpt } from '../../llms/gpt';
import '../modal-auth/modal-auth';
import {
  ModelFamily,
  SupportedLocalModel,
  supportedModelReverseLookup,
  SupportedRemoteModel,
  UserConfig
} from '../wordflow/user-config';
import { diff_wordMode_ } from './text-diff';
import { WELCOME_TEXT } from './welcome-text';

// Editor
import { Editor, JSONContent, posToDOMRect } from '@tiptap/core';
import Paragraph from '@tiptap/extension-paragraph';
import Placeholder from '@tiptap/extension-placeholder';
import Text from '@tiptap/extension-text';
import { closeHistory } from '@tiptap/pm/history';
import { TextSelection } from '@tiptap/pm/state';
import StarterKit from '@tiptap/starter-kit';
import { Collapse } from './collapse-node';
import { EditHighlight } from './edit-highlight';
import { LoadingHighlight } from './loading-highlight';
import { SidebarMenu } from './sidebar-menu-plugin';

// Types
import type { ResolvedPos } from '@tiptap/pm/model';
import type { EditorView } from '@tiptap/pm/view';
import type { GptModel, TextGenMessage } from '../../llms/gpt';
import type { TextGenLocalWorkerMessage } from '../../llms/web-llm';
import type { PromptModel, SimpleEventMessage } from '../../types/common-types';
import type { PromptDataLocal } from '../../types/wordflow';
import type { PromptManager } from '../wordflow/prompt-manager';
import type {
  UpdateContextualChatProps,
  ToastMessage,
  UpdateSidebarMenuProps
} from '../wordflow/wordflow';
import type { CollapseAttributes } from './collapse-node';
import type { EditHighlightAttributes } from './edit-highlight';
import type { PopperOptions } from './sidebar-menu-plugin';

// CSS
import { style } from '../../../node_modules/@tiptap/core/src/style';
import componentCSS from './text-editor.css?inline';

const ADDED_COLOR = config.customColors.addedColor;
const REPLACED_COLOR = config.customColors.replacedColor;
const INPUT_TEXT_PLACEHOLDER = '{{text}}';

const DEV_MODE = import.meta.env.DEV;
const USE_CACHE = true && DEV_MODE;
const DMP = new DiffMatchPatch();

export interface AiEditContext {
  action: string;
  scope: 'selection' | 'paragraph';
  selected_text: string;
  result_text: string;
}

export interface DocumentSnapshot {
  content_html: string;
  content_text: string;
}

/**
 * Text editor element.
 *
 */
@customElement('wordflow-text-editor')
export class WordflowTextEditor extends LitElement {
  //==========================================================================||
  //                              Class Properties                            ||
  //==========================================================================||
  @property({ attribute: false })
  popperSidebarBox: Promise<HTMLElement> | undefined;

  @property({ attribute: false })
  updateSidebarMenu:
    | ((props: UpdateSidebarMenuProps) => Promise<void>)
    | undefined;

  @property({ attribute: false })
  updateContextualChat:
    | ((props: UpdateContextualChatProps) => void)
    | undefined;

  @property({ attribute: false })
  promptManager!: PromptManager;

  @property({ attribute: false })
  userConfig!: UserConfig;

  @property({ attribute: false })
  textGenLocalWorker!: Worker;
  textGenLocalWorkerResolve = (
    value: TextGenMessage | PromiseLike<TextGenMessage>
  ) => {};

  @property({ type: Boolean })
  isAuthorized = false;

  @query('.text-editor-container')
  containerElement: HTMLElement | undefined;

  @query('.text-editor')
  editorElement: HTMLElement | undefined;

  @query('.select-menu')
  selectMenuElement: HTMLElement | undefined;

  @state()
  isHoveringFloatingMenu = false;

  editor: Editor | null = null;
  curEditID = 0;
  lastAiEditContext: AiEditContext | null = null;

  containerBBox: DOMRect = {
    x: 0,
    y: 0,
    width: 0,
    height: 0,
    bottom: 0,
    left: 0,
    top: 0,
    right: 0,
    toJSON: () => ''
  };

  //==========================================================================||
  //                             Lifecycle Methods                            ||
  //==========================================================================||
  constructor() {
    super();
  }

  firstUpdated() {
    this.initEditor();

    window.addEventListener('beforeunload', () => {
      if (this.editor !== null && this.isAuthorized) {
        // Save the editor's content to local storage
        const content = this.editor.getJSON();
        localStorage.setItem('last-editor-content', JSON.stringify(content));
      }
    });

    // Add event listener to the local text gen worker
    this.textGenLocalWorker.addEventListener(
      'message',
      (e: MessageEvent<TextGenLocalWorkerMessage>) => {
        this.textGenLocalWorkerMessageHandler(e);
      }
    );
  }

  initEditor() {
    if (
      this.editorElement === undefined ||
      this.selectMenuElement === undefined ||
      this.containerElement === undefined ||
      this.popperSidebarBox === undefined ||
      this.updateSidebarMenu === undefined
    ) {
      console.error(
        'Text editor / select menu element is not added to DOM yet!'
      );
      return;
    }

    // Store the x position of th left and right border of the container element
    this.containerBBox = this.containerElement.getBoundingClientRect();

    // Register keyboard shortcuts
    const myText = Text.extend({
      addKeyboardShortcuts() {
        return {};
      }
    });

    const myParagraph = Paragraph.extend({
      addAttributes() {
        return {
          ...this.parent?.(),
          'is-highlighted': {
            default: null,
            parseHTML: element => element.getAttribute('is-highlighted'),
            renderHTML: attributes => {
              return {
                class: attributes['is-highlighted'] ? 'is-highlighted' : null
              };
            }
          },
          'is-loading': {
            default: null,
            parseHTML: element => element.getAttribute('is-loading'),
            renderHTML: attributes => {
              return {
                class: attributes['is-loading'] ? 'is-loading' : null
              };
            }
          }
        };
      }
    });

    // Customize the StarterKit extension to exclude customized extensions
    const myStarterKit = StarterKit.configure({
      text: false,
      paragraph: false
    });

    const myEditHighlight = EditHighlight.configure({
      multicolor: true
    });

    const myLoadingHighlight = LoadingHighlight.configure({});

    const popperOptions: PopperOptions = {
      popperSidebarBox: this.popperSidebarBox,
      containerBBox: this.containerBBox,
      updateSidebarMenu: this.updateSidebarMenu
    };

    const mySidebarMenu = SidebarMenu.configure({
      popperOptions
    });

    let defaultText: string | JSONContent = '';
    const lastEditorContent = this.getLocalEditorSnapshot();
    if (lastEditorContent !== null) {
      defaultText = lastEditorContent;
    }

    const hasRunAPrompt = localStorage.getItem('has-run-a-prompt');
    if (lastEditorContent === null && hasRunAPrompt === null) {
      defaultText = `${WELCOME_TEXT}`;
    }

    if (DEV_MODE) {
      defaultText = `${WELCOME_TEXT}`;
    }

    const myPlaceholder = Placeholder.configure({
      placeholder: 'Type or paste your text here to start...'
    });

    this.editor = new Editor({
      element: this.editorElement,
      extensions: [
        myStarterKit,
        myParagraph,
        myText,
        myEditHighlight,
        myLoadingHighlight,
        Collapse,
        mySidebarMenu,
        myPlaceholder
      ],
      content: defaultText,
      editable: this.isAuthorized,
      autofocus: this.isAuthorized,
      onSelectionUpdate: () => this.notifyContextualChat(false),
      editorProps: {
        handleKeyDown: (_view, event) =>
          this.contextualChatKeydownHandler(event)
      }
    });
  }

  /**
   * This method is called before new DOM is updated and rendered
   * @param changedProperties Property that has been changed
   */
  willUpdate(changedProperties: PropertyValues<this>) {}

  updated(changedProperties: PropertyValues<this>) {
    if (changedProperties.has('isAuthorized')) {
      if (this.editor !== null) {
        this.editor.setEditable(this.isAuthorized);
      }
      if (!this.isAuthorized) {
        this.updateContextualChat?.({ visible: false });
      }
    }
  }

  //==========================================================================||
  //                              Custom Methods                              ||
  //==========================================================================||
  async initData() {}

  contextualChatKeydownHandler(event: KeyboardEvent) {
    if (!this.isAuthorized) {
      this.updateContextualChat?.({ visible: false });
      return false;
    }

    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'j') {
      event.preventDefault();
      this.notifyContextualChat(true);
      return true;
    }
    return false;
  }

  notifyContextualChat(open: boolean) {
    if (this.editor === null || this.updateContextualChat === undefined) return;
    if (!this.isAuthorized) {
      this.updateContextualChat({ visible: false });
      return;
    }

    const { state, view } = this.editor;
    const { selection } = state;
    const hasSelection = !selection.empty;

    if (!hasSelection) {
      this.updateContextualChat({ visible: false });
      return;
    }

    const rect = hasSelection
      ? posToDOMRect(view, selection.from, selection.to)
      : view.coordsAtPos(selection.from);
    const rectWidth = 'width' in rect ? rect.width : rect.right - rect.left;
    const rectHeight = 'height' in rect ? rect.height : rect.bottom - rect.top;
    const selectedText = hasSelection
      ? state.doc.textBetween(selection.from, selection.to, '\n\n')
      : '';
    const contextBefore = state.doc.textBetween(
      Math.max(0, selection.from - 500),
      selection.from,
      '\n\n'
    );
    const contextAfter = state.doc.textBetween(
      selection.to,
      Math.min(state.doc.content.size, selection.to + 500),
      '\n\n'
    );

    this.updateContextualChat({
      visible: true,
      open,
      rect: {
        left: rect.left,
        right: rect.right,
        top: rect.top,
        bottom: rect.bottom,
        width: rectWidth,
        height: rectHeight
      },
      selection: selectedText
        ? {
            text: selectedText,
            context_before: contextBefore,
            context_after: contextAfter
          }
        : null
    });
  }

  diffParagraph(oldText: string, newText: string) {
    // const differences = diff_wordMode_(oldText, newText);
    const differences = DMP.diff_main(oldText, newText);
    DMP.diff_cleanupSemantic(differences);

    // Organize the text to highlight the new text and keep track of their
    // old text
    // Case 1: delete old, add new => show add
    // Case 2: delete old => show icon
    // Case 3: add new => show new
    // Note that diff-match-patch use -1, 0, 1 to encode delete, no change, and add.
    // We can add these numbers to distinguish the three cases above.
    let diffText = '';
    let lastDeletedText = '';
    const replaceMap = new Map<string, string>();

    for (const [i, diff] of differences.entries()) {
      switch (diff[0]) {
        case 0: {
          // No change
          diffText += diff[1];
          lastDeletedText = '';
          break;
        }

        case -1: {
          // Deleted
          lastDeletedText = diff[1];

          // Case 2: delete old => show icon
          // Check if the deleted text is not replaced by new text
          if (i + 1 >= differences.length || differences[i + 1][0] === 0) {
            diffText += `<span
              id="collapse-${this.curEditID++}"
              data-type="collapse"
              deleted-text="${diff[1]}"
            ></span>`;
          }
          break;
        }

        case 1: {
          // Added

          // Special case: if the new content is a new line, ignore it
          if (diff[1] === '\n\n') {
            diffText += diff[1];
            continue;
          }

          // Case 1: delete old, add new => show add
          // Also record the original old text
          if (i >= 1 && differences[i - 1][0] === -1) {
            diffText += `<mark
              id="edit-highlight-${this.curEditID++}"
              data-color="${REPLACED_COLOR}"
              data-old-text="${lastDeletedText}"
            >${diff[1]}</mark>`;
            replaceMap.set(diff[1], lastDeletedText);
            lastDeletedText = '';
          }

          // Case 3: add new => show new
          // Add empty string as the old text
          if (i >= 1 && differences[i - 1][0] === 0) {
            if (diff[1] === ' ') {
              // Temporary fix: add the new space as old text, because <mark> with
              // space content is not be rendered by tiptap.
              diffText += ' ';
              replaceMap.set(diff[1], '');
              lastDeletedText = '';
            } else {
              diffText += `<mark
              id="edit-highlight-${this.curEditID++}"
              data-color="${ADDED_COLOR}"
              data-old-text="${lastDeletedText}"
            >${diff[1]}</mark>`;
              replaceMap.set(diff[1], '');
              lastDeletedText = '';
            }
          }

          // Case 4: no old, add new => show new
          if (i === 0) {
            diffText += `<mark
              id="edit-highlight-${this.curEditID++}"
              data-color="${ADDED_COLOR}"
              data-old-text="${lastDeletedText}"
            >${diff[1]}</mark>`;
            replaceMap.set(diff[1], '');
            lastDeletedText = '';
          }

          break;
        }

        default: {
          console.error('Unknown diff code', diff);
        }
      }
    }

    // If the paragraph ends with a mark element, add a trailing space to exit
    // the mark
    if (diffText.slice(-7) === '</mark>') {
      diffText += '&nbsp;';
    }

    return diffText;
  }

  /**
   * Detection if the users has not selected anything
   * @returns True if there is empty selection
   */
  isEmptySelection() {
    if (this.editor === null) {
      console.error('Editor is not initialized yet.');
      return;
    }
    const { $from, $to } = this.editor.view.state.selection;
    let hasSelection = $from.pos !== $to.pos;
    // If the user select the collapse node, the selection range is also 1
    if (Math.abs($from.pos - $to.pos) === 1) {
      const node = $from.nodeAfter;
      if (node && node.type.name === 'collapse') {
        hasSelection = false;
      }
    }
    return hasSelection;
  }

  /**
   * Accept the current active edit (replace, add, or delete)
   */
  acceptChange() {
    if (this.editor === null) {
      throw Error('Editor is not fully initialized');
    }

    const view = this.editor.view;
    const state = view.state;
    const selection = state.selection;
    const { $from } = selection;

    const isActive = this._isEditActive();
    if (!isActive) {
      return;
    }

    // To accept the change, we only need to remove the mark or the node
    if (this.editor.isActive('edit-highlight')) {
      this.editor
        .chain()
        .focus()
        .unsetMark('edit-highlight', { extendEmptyMarkRange: true })
        .run();
    } else if (this.editor.isActive('collapse')) {
      // Move the cursor
      const newSelection = TextSelection.create(state.doc, $from.pos);
      const tr = state.tr;
      tr.setSelection(newSelection);
      // Remove the node
      tr.delete($from.pos, $from.pos + 1);
      view.dispatch(tr);
      view.focus();
    }
  }

  /**
   * Reject the current active edit (replace, add, or delete)
   */
  rejectChange() {
    if (this.editor === null) {
      throw Error('Editor is not fully initialized');
    }

    const view = this.editor.view;
    const state = view.state;
    const { selection, schema } = state;
    const { $from } = selection;

    const isActive = this._isEditActive();
    if (!isActive) {
      return;
    }

    // To reject a change, we need to replace the new content with old text
    if (this.editor.isActive('edit-highlight')) {
      const mark = $from.marks()[0];
      const markAttribute = mark.attrs as EditHighlightAttributes;
      // Find the range of the mark
      let from = -1;
      let to = -1;
      state.doc.content.descendants((node, pos) => {
        if (
          node.marks.some(
            m => (m.attrs as EditHighlightAttributes).id === markAttribute.id
          )
        ) {
          from = pos;
          to = pos + node.nodeSize;
          return false;
        }
      });

      // Replace the text content in the highlight with the old text
      const tr = state.tr;

      if (markAttribute.oldText.length > 0) {
        // Reject replacement
        const newText = schema.text(markAttribute.oldText);
        const newSelection = TextSelection.create(
          state.doc,
          from + newText.nodeSize
        );
        // Need to set the selection before replacing the text
        tr.setSelection(newSelection);
        tr.replaceWith(from, to, newText);
      } else {
        // Reject addition
        tr.delete(from, to);
      }
      view.dispatch(tr);
      view.focus();
    } else if (this.editor.isActive('collapse')) {
      // Remove the node
      const node = $from.nodeAfter!;
      const nodeAttrs = node.attrs as CollapseAttributes;

      // Move the cursor
      const newSelection = TextSelection.create(state.doc, $from.pos);
      const tr = state.tr;
      tr.setSelection(newSelection);

      // Remove the node
      tr.delete($from.pos, $from.pos + 1);

      // Add new text node
      const newText = schema.text(nodeAttrs['deleted-text']);
      tr.insert($from.pos, newText);
      view.dispatch(tr);
      view.focus();
    }
  }

  /**
   * Accept all edits in the selection (replace, add, or delete)
   */
  acceptAllChanges() {
    if (this.editor === null) {
      throw Error('Editor is not fully initialized');
    }

    const view = this.editor.view;
    const state = view.state;
    const selection = state.selection;
    const { $from, $to } = selection;
    const tr = state.tr;

    // Remove all the marks
    const markType = state.schema.marks['edit-highlight'];
    tr.removeMark($from.pos, $to.pos, markType);

    // Remove all the collapse nodes
    let positions: number[] = [];
    state.doc.nodesBetween($from.pos, $to.pos, (node, pos) => {
      if (node.type.name === 'collapse') {
        positions.push(pos);
      }
    });

    // Delete from the end to not mess up the pos index
    positions = positions.reverse();

    for (const pos of positions) {
      const node = state.doc.nodeAt(pos);
      if (node) {
        tr.delete(pos, pos + node.nodeSize);
      }
    }

    view.dispatch(tr);
    view.focus();
  }

  /**
   * Reject all edits in the selection (replace, add, or delete)
   */
  rejectAllChanges() {
    if (this.editor === null) {
      throw Error('Editor is not fully initialized');
    }

    const view = this.editor.view;
    const state = view.state;
    const { selection, schema } = state;
    const { $from, $to } = selection;
    const tr = state.tr;

    // To reject a change, we need to replace the new content with old text
    let posOffset = 0;

    state.doc.nodesBetween($from.pos, $to.pos, (node, pos) => {
      // Reject adds and replacement
      for (const mark of node.marks) {
        const markAttribute = mark.attrs as EditHighlightAttributes;
        if (mark.type.name === 'edit-highlight') {
          const markFrom = pos + posOffset;
          const markTo = pos + node.nodeSize + posOffset;

          if (markAttribute.oldText.length === 0) {
            // If the old text is empty, delete this mark node
            tr.delete(markFrom, markTo);
            posOffset -= node.nodeSize;
          } else {
            const newText = schema.text(markAttribute.oldText);
            tr.replaceWith(markFrom, markTo, newText);
            posOffset = posOffset - node.nodeSize + newText.nodeSize;
          }
        }
      }

      // Reject deletions
      if (node.type.name === 'collapse') {
        const nodeAttrs = node.attrs as CollapseAttributes;
        const newText = schema.text(nodeAttrs['deleted-text']);
        const nodeFrom = pos + posOffset;
        const nodeTo = pos + node.nodeSize + posOffset;

        tr.replaceWith(nodeFrom, nodeTo, newText);
        posOffset = posOffset - node.nodeSize + newText.nodeSize;
      }
    });

    view.dispatch(tr);
    view.focus();
  }

  //==========================================================================||
  //                               Event Handlers                             ||
  //==========================================================================||
  /**
   * Event handler for the text gen local worker
   * @param e Text gen message
   */
  textGenLocalWorkerMessageHandler(e: MessageEvent<TextGenLocalWorkerMessage>) {
    switch (e.data.command) {
      case 'finishTextGen': {
        const message: TextGenMessage = {
          command: 'finishTextGen',
          payload: e.data.payload
        };
        this.textGenLocalWorkerResolve(message);
        break;
      }

      case 'progressLoadModel': {
        break;
      }

      case 'finishLoadModel': {
        break;
      }

      case 'error': {
        const message: TextGenMessage = {
          command: 'error',
          payload: e.data.payload
        };
        this.textGenLocalWorkerResolve(message);
        break;
      }

      default: {
        console.error('Worker: unknown message', e.data.command);
        break;
      }
    }
  }

  sidebarMenuFooterButtonClickedHandler(e: CustomEvent<string>) {
    switch (e.detail) {
      case 'accept': {
        this.acceptChange();
        break;
      }

      case 'reject': {
        this.rejectChange();
        break;
      }

      case 'accept-all': {
        this.acceptAllChanges();
        break;
      }

      case 'reject-all': {
        this.rejectAllChanges();
        break;
      }

      default: {
        console.error('Unknown button clicked:', e.detail);
      }
    }
  }

  getDocumentSnapshot() {
    if (this.editor === null) {
      return { content_html: '', content_text: '' };
    }
    return {
      content_html: this.editor.getHTML(),
      content_text: this.editor.getText()
    };
  }

  loadDocumentHtml(contentHtml: string) {
    if (this.editor === null) return;
    this.editor.commands.setContent(contentHtml || '');
    const content = this.editor.getJSON();
    localStorage.setItem('last-editor-content', JSON.stringify(content));
  }

  getLocalEditorSnapshot(): JSONContent | null {
    const lastEditorContent = localStorage.getItem('last-editor-content');
    if (lastEditorContent === null) return null;
    try {
      return JSON.parse(lastEditorContent) as JSONContent;
    } catch (error) {
      console.warn('Failed to parse last-editor-content', error);
      localStorage.removeItem('last-editor-content');
      return null;
    }
  }

  restoreLocalEditorSnapshot() {
    if (this.editor === null) return false;
    const lastEditorContent = this.getLocalEditorSnapshot();
    if (lastEditorContent === null) return false;
    this.editor.commands.setContent(lastEditorContent);
    return true;
  }

  getCleanDocumentSnapshot(): DocumentSnapshot {
    const snapshot = this.getDocumentSnapshot();
    return this._cleanDiffHtmlSnapshot(snapshot.content_html);
  }

  dispatchAiEditAccepted(detail: {
    action: string;
    document_id: number;
    base_version_id: number;
    content_html: string;
    content_text: string;
    selected_text: string;
    result_text: string;
  }) {
    this.dispatchEvent(
      new CustomEvent('ai-edit-accepted', {
        detail,
        bubbles: true,
        composed: true
      })
    );
  }

  dispatchAiEditRejected(action: string) {
    this.dispatchEvent(
      new CustomEvent('ai-edit-rejected', {
        detail: { action },
        bubbles: true,
        composed: true
      })
    );
  }

  /**
   * Highlight the currently effective selection. It is the user's selected
   * text or the current paragraph (if there is no selection).
   */
  floatingMenuToolsMouseEnterHandler() {
    if (!this.isAuthorized) return;
    if (this.editor === null) {
      console.error('Editor is not initialized yet.');
      return;
    }
    this.isHoveringFloatingMenu = true;
    const { $from, $to } = this.editor.view.state.selection;
    const hasSelection = this.isEmptySelection();

    // Highlight the paragraph
    if (!hasSelection) {
      const node = $from.node();
      if (node.content.size > 0) {
        this._setParagraphAttribute($from, 'is-highlighted', 'true');
      }
    }
  }

  /**
   * Cancel any highlighting set from mouseenter
   */
  floatingMenuToolsMouseLeaveHandler() {
    if (!this.isAuthorized) return;
    if (this.editor === null) {
      console.error('Editor is not initialized yet.');
      return;
    }
    this.isHoveringFloatingMenu = false;
    const { $from, $to } = this.editor.view.state.selection;
    const hasSelection = this.isEmptySelection();

    // Highlight the paragraph
    if (!hasSelection) {
      this._setParagraphAttribute($from, 'is-highlighted', null);
    }
  }

  /**
   * Execute the prompt on the selected text
   */
  floatingMenuToolButtonClickHandler(promptData: PromptDataLocal) {
    if (!this.isAuthorized) {
      const event = new CustomEvent<ToastMessage>('show-toast', {
        bubbles: true,
        composed: true,
        detail: {
          message: 'Please sign in before writing',
          type: 'warning'
        }
      });
      this.dispatchEvent(event);
      return;
    }

    if (this.editor === null) {
      console.error('Editor is not initialized yet.');
      return;
    }

    const { state } = this.editor.view;
    const { $from, $to } = state.selection;
    const hasSelection = this.isEmptySelection();

    // Paragraph mode
    if (!hasSelection) {
      // Change the highlight style
      this._setParagraphAttribute($from, 'is-highlighted', null);

      if ($from.node().content.size > 0) {
        this._setParagraphAttribute($from, 'is-loading', 'true');
      }

      // Find the paragraph node of the cursor's region
      const paragraphNode = $from.node(1);
      const paragraphPos = $from.before(1);

      const oldText = paragraphNode.textContent;
      const runRequest = this._runPrompt(promptData, oldText);

      runRequest.then(message => {
        // Cancel the loading style
        this._setParagraphAttribute($from, 'is-loading', null);
        this._dispatchLoadingFinishedEvent();

        switch (message.command) {
          case 'finishTextGen': {
            // Success
            if (this.editor === null) {
              console.error('Editor is not initialized');
              return;
            }

            if (DEV_MODE) {
              console.info(
                `Finished running prompt with [${this.userConfig.preferredLLM}]`
              );
              console.info(message.payload.result);
            }

            let newText = this._parseOutput(promptData, message.payload.result);

            // Append the output to the end of the input text if the prompt
            // uses append mode
            if (promptData.injectionMode === 'append') {
              if (oldText !== '') {
                newText = oldText + '\n' + newText;
              }
            }
            this.lastAiEditContext = {
              action: this._promptActionKey(promptData),
              scope: 'paragraph',
              selected_text: oldText,
              result_text: newText
            };

            let diffText = this.diffParagraph(oldText, newText);
            diffText = `<p>${diffText}</p>`;

            this.editor
              .chain()
              .focus()
              .insertContentAt(
                {
                  from: paragraphPos,
                  to: paragraphPos + paragraphNode.nodeSize
                },
                diffText,
                { updateSelection: true }
              )
              .run();

            this._updateAfterSuccessfulPromptRun(promptData);
            break;
          }

          case 'error': {
            this._handleError(message.payload.message);
          }
        }
      });
    } else {
      // Selection mode
      // Set the highlight
      this.editor
        .chain()
        .focus()
        .setMeta('addToHistory', false)
        .setMark('loading-highlight')
        .run();

      // Generate new text
      const oldText = state.doc.textBetween($from.pos, $to.pos);
      const runRequest = this._runPrompt(promptData, oldText);

      runRequest.then(message => {
        if (this.editor === null) {
          console.error('Editor is not initialized yet.');
          return;
        }
        this._dispatchLoadingFinishedEvent();

        // Remove the highlight
        this.editor
          .chain()
          .focus()
          .setMeta('addToHistory', false)
          .unsetMark('loading-highlight', { extendEmptyMarkRange: true })
          .run();

        switch (message.command) {
          case 'finishTextGen': {
            if (this.editor === null) {
              console.error('Editor is not initialized');
              return;
            }

            if (DEV_MODE) {
              console.info(message.payload.result);
            }

            let newText = this._parseOutput(promptData, message.payload.result);
            // Append the output to the end of the input text if the prompt
            // uses append mode
            if (promptData.injectionMode === 'append') {
              newText = oldText + ' ' + newText;
            }
            this.lastAiEditContext = {
              action: this._promptActionKey(promptData),
              scope: 'selection',
              selected_text: oldText,
              result_text: newText
            };

            let diffText = this.diffParagraph(oldText, newText);
            diffText = `${diffText}`;

            const diffTextChunks = diffText.split('\n\n');
            if (diffTextChunks.length > 1) {
              let newDiffText = '';
              for (const [i, chunk] of diffTextChunks.entries()) {
                if (i === 0) {
                  // First chunk
                  newDiffText += `${chunk}<p></p>`;
                } else if (i === diffTextChunks.length - 1) {
                  // Last chunk
                  newDiffText += `${chunk}`;
                } else {
                  newDiffText += `<p>${chunk}</p><p></p>`;
                }
              }
              diffText = newDiffText;
            }

            this.editor
              .chain()
              .focus()
              .insertContentAt(
                {
                  from: $from.pos,
                  to: $to.pos
                },
                diffText,
                { updateSelection: true }
              )
              .joinBackward()
              .run();

            this._updateAfterSuccessfulPromptRun(promptData);
            break;
          }

          case 'error': {
            this._handleError(message.payload.message);
          }
        }
      });
    }
  }

  //==========================================================================||
  //                             Private Helpers                              ||
  //==========================================================================||

  _cleanDiffHtmlSnapshot(contentHtml: string): DocumentSnapshot {
    const template = document.createElement('template');
    template.innerHTML = contentHtml;

    for (const mark of Array.from(template.content.querySelectorAll('mark'))) {
      const oldText = mark.getAttribute('data-old-text') ?? '';
      if (oldText.length > 0) {
        mark.replaceWith(document.createTextNode(oldText));
      } else {
        mark.remove();
      }
    }

    for (const collapse of Array.from(
      template.content.querySelectorAll('span[data-type="collapse"]')
    )) {
      collapse.replaceWith(
        document.createTextNode(collapse.getAttribute('deleted-text') ?? '')
      );
    }

    const container = document.createElement('div');
    container.append(template.content.cloneNode(true));
    return {
      content_html: container.innerHTML,
      content_text: container.textContent ?? ''
    };
  }

  _promptActionKey(promptData: PromptDataLocal) {
    const scriptAction = promptData.tags?.find(tag =>
      ['expand', 'rewrite', 'oralize', 'shorten'].includes(tag)
    );
    if (scriptAction) return scriptAction;
    return promptData.key.replace(/^script-action-/, '') || promptData.title;
  }

  /**
   * Run the given prompt using the preferred model
   * @returns A promise of the prompt inference
   */
  _runPrompt(promptData: PromptDataLocal, inputText: string) {
    const curPrompt = this._formatPrompt(
      promptData.prompt,
      inputText,
      INPUT_TEXT_PLACEHOLDER
    );

    let runRequest: Promise<TextGenMessage>;

    switch (this.userConfig.preferredLLM) {
      case SupportedRemoteModel['gpt-5-nano-free']: {
        // Backend-managed default: let the server pick its configured model
        // (OPENAI_MODEL) instead of routing through the retired community
        // "free tier" endpoint.
        runRequest = textGenGpt(
          this.userConfig.llmAPIKeys[ModelFamily.openAI],
          'text-gen',
          curPrompt,
          promptData.temperature,
          '' as GptModel,
          USE_CACHE
        );
        break;
      }

      case SupportedRemoteModel['gpt-5.4']:
      case SupportedRemoteModel['gpt-5.4-pro']:
      case SupportedRemoteModel['gpt-5.4-mini']:
      case SupportedRemoteModel['gpt-5.4-nano']:
      case SupportedRemoteModel['gpt-5-mini']:
      case SupportedRemoteModel['gpt-5-nano']:
      case SupportedRemoteModel['gpt-5']:
      case SupportedRemoteModel['gpt-4.1']: {
        runRequest = textGenGpt(
          this.userConfig.llmAPIKeys[ModelFamily.openAI],
          'text-gen',
          curPrompt,
          promptData.temperature,
          supportedModelReverseLookup[this.userConfig.preferredLLM] as GptModel,
          USE_CACHE
        );
        break;
      }

      case SupportedRemoteModel['gemini-pro']: {
        runRequest = textGenGemini(
          this.userConfig.llmAPIKeys[ModelFamily.google],
          'text-gen',
          curPrompt,
          promptData.temperature,
          USE_CACHE
        );
        break;
      }

      // case SupportedLocalModel['mistral-7b-v0.2']:
      case SupportedLocalModel['gemma-2b']:
      case SupportedLocalModel['phi-2']:
      case SupportedLocalModel['llama-2-7b']:
      case SupportedLocalModel['tinyllama-1.1b']: {
        runRequest = new Promise<TextGenMessage>(resolve => {
          this.textGenLocalWorkerResolve = resolve;
        });
        const message: TextGenLocalWorkerMessage = {
          command: 'startTextGen',
          payload: {
            apiKey: '',
            prompt: curPrompt,
            requestID: '',
            temperature: promptData.temperature
          }
        };
        this.textGenLocalWorker.postMessage(message);
        break;
      }

      default: {
        console.error('Unknown case ', this.userConfig.preferredLLM);
        runRequest = textGenGpt(
          this.userConfig.llmAPIKeys[ModelFamily.openAI],
          'text-gen',
          curPrompt,
          promptData.temperature,
          'gpt-5.4-mini',
          USE_CACHE
        );
      }
    }
    return runRequest;
  }

  /**
   * Show a toast when the API call is timed out
   * @param errorMessage Error message
   */
  _handleError(errorMessage: string) {
    console.error('Failed to generate text', errorMessage);

    let message = 'Failed to run this prompt. Try again later.';

    if (errorMessage === 'time out') {
      message = 'Fail to run this prompt (OpenAI API timed out!)';
    }

    if (errorMessage === 'Rate limit exceeded.') {
      message = 'You have run too many prompts. Try again later.';
    }
    // Show a toast
    const event = new CustomEvent<ToastMessage>('show-toast', {
      bubbles: true,
      composed: true,
      detail: {
        message,
        type: 'error'
      }
    });
    this.dispatchEvent(event);
  }

  /**
   * Increase the prompt run count by 1
   * @param promptData Prompt data
   */
  _updateAfterSuccessfulPromptRun(promptData: PromptDataLocal) {
    if (this.editor === null) {
      console.error('Editor is not initialized yet.');
      return;
    }

    const newPrompt = structuredClone(promptData);
    newPrompt.promptRunCount += 1;
    this.promptManager.setPrompt(newPrompt);

    // Also update the local storage
    localStorage.setItem('has-run-a-prompt', 'true');

    // Save the editor's content to local storage
    const content = this.editor.getJSON();
    localStorage.setItem('last-editor-content', JSON.stringify(content));
  }

  /**
   * Combine prompt prefix and the input text
   * @param prompt Prompt prefix
   * @param inputText Input text
   * @param placeholder Placeholder string
   * @returns Formatted prompt
   */
  _formatPrompt(prompt: string, inputText: string, placeholder: string) {
    let curPrompt = '';
    if (prompt.includes(placeholder)) {
      curPrompt = prompt.replace(placeholder, inputText);
    } else {
      curPrompt = prompt + '\n' + inputText;
    }
    return curPrompt;
  }

  /**
   * Parse an LLM output using rules defined in a prompt
   * @param prompt Prompt data
   * @param output LLM output
   */
  _parseOutput(prompt: PromptDataLocal, output: string) {
    if (prompt.outputParsingPattern === '') {
      return output;
    }

    const pattern = new RegExp(prompt.outputParsingPattern);
    let replacement = prompt.outputParsingReplacement;
    if (replacement === '') {
      replacement = '$1';
    }

    const outputText = output.replace(pattern, replacement);
    return outputText;
  }

  /**
   * Helper method to check if the user has selected an edit
   * @returns True if an edit is actively selected
   */
  _isEditActive() {
    if (this.editor === null) {
      throw Error('Editor is not fully initialized');
    }

    const view = this.editor.view;
    const selection = view.state.selection;
    const { $from } = selection;

    let isActive = false;
    if (this.editor.isActive('edit-highlight')) {
      if ($from.marks().length > 0) {
        isActive = true;
      }
    } else if (this.editor.isActive('collapse')) {
      if ($from.nodeAfter !== null) {
        isActive = true;
      }
    }

    return isActive;
  }

  /**
   * Set the attribute of the current paragraph node
   * @param $from From position of the selection
   * @param attribute Attribute name
   * @param value Attribute value
   * @returns void
   */
  _setParagraphAttribute(
    $from: ResolvedPos,
    attribute: string,
    value: string | null
  ) {
    if (this.editor === null) {
      console.error('Editor is not initialized yet.');
      return;
    }

    // Find the paragraph node of the cursor's region
    const paragraphNode = $from.node(1);
    const paragraphPos = $from.before(1);

    // Update the node's attributes to include the highlighted class
    const updatedAttrs = {
      ...paragraphNode.attrs
    };
    updatedAttrs[attribute] = value;

    const tr = this.editor.view.state.tr;
    tr.setNodeMarkup(paragraphPos, null, updatedAttrs);
    tr.setMeta('addToHistory', false);
    this.editor.view.dispatch(tr);
  }

  /**
   * Notify the parent that the loading is finished.
   */
  _dispatchLoadingFinishedEvent() {
    const event = new Event('loading-finished', {
      bubbles: true,
      composed: true
    });
    this.dispatchEvent(event);
  }

  //==========================================================================||
  //                           Templates and Styles                           ||
  //==========================================================================||
  render() {
    return html` <div class="text-editor-container">
      <div
        class="text-editor"
        contenteditable="false"
        ?is-hovering-floating-menu=${this.isHoveringFloatingMenu}
      ></div>
    </div>`;
  }

  static styles = [
    css`
      ${unsafeCSS(componentCSS)}
      ${unsafeCSS(style)}
    `
  ];
}

declare global {
  interface HTMLElementTagNameMap {
    'wordflow-text-editor': WordflowTextEditor;
  }
}

/**
 * Parse content inside an XML tag
 * @param text LLM response text
 * @param tag XML tag to parse
 * @returns A list of content in the parsed tags
 */
export const parseTags = (text: string, tag: string) => {
  const regex = new RegExp(`<${tag}>\\s*(.*)\\s*</${tag}>`, 'g');
  const matches = text.match(regex) || [];
  return matches.map(match => match.replace(regex, '$1'));
};
