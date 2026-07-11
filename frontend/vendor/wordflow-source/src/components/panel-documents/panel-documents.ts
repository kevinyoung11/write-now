import { LitElement, css, unsafeCSS, html, PropertyValues } from 'lit';
import { customElement, property, query } from 'lit/decorators.js';
import { unsafeHTML } from 'lit/directives/unsafe-html.js';

import '../confirm-dialog/confirm-dialog';

// Types
import type { DocumentListItemPayload } from '../../product/document-client';
import type {
  NightjarConfirmDialog,
  DialogInfo
} from '../confirm-dialog/confirm-dialog';

// Assets
import componentCSS from './panel-documents.css?inline';
import addIcon from '../../images/icon-plus-circle.svg?raw';
import deleteIcon from '../../images/icon-delete.svg?raw';
import noteIcon from '../../images/icon-home.svg?raw';

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  month: 'short',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit'
});

const formatUpdatedAt = (updatedAt: string | undefined): string => {
  if (!updatedAt) return '';
  const date = new Date(updatedAt);
  if (Number.isNaN(date.getTime())) return '';
  return dateFormatter.format(date);
};

/**
 * Lists the user's saved documents so they can switch between them, start a
 * new one, or delete old ones.
 */
@customElement('wordflow-panel-documents')
export class WordflowPanelDocuments extends LitElement {
  //==========================================================================||
  //                              Class Properties                            ||
  //==========================================================================||
  @property({ attribute: false })
  documentList: DocumentListItemPayload[] = [];

  @property({ type: Boolean })
  documentListLoading = false;

  @property({ attribute: false })
  currentDocumentId: number | null = null;

  @property({ attribute: false })
  onSelectDocument: ((documentId: number) => void) | undefined;

  @property({ attribute: false })
  onCreateDocument: (() => void) | undefined;

  @property({ attribute: false })
  onDeleteDocument: ((documentId: number) => void) | undefined;

  @query('nightjar-confirm-dialog')
  confirmDialogComponent: NightjarConfirmDialog | undefined;

  //==========================================================================||
  //                             Lifecycle Methods                            ||
  //==========================================================================||
  constructor() {
    super();
  }

  willUpdate(changedProperties: PropertyValues<this>) {}

  //==========================================================================||
  //                              Event Handlers                              ||
  //==========================================================================||
  documentClicked(documentId: number) {
    this.onSelectDocument?.(documentId);
  }

  createButtonClicked() {
    this.onCreateDocument?.();
  }

  deleteButtonClicked(e: MouseEvent, documentData: DocumentListItemPayload) {
    e.stopPropagation();

    if (this.confirmDialogComponent === undefined) {
      throw Error('confirmDialogComponent is undefined');
    }

    const dialogInfo: DialogInfo = {
      header: 'Delete Note',
      message: `Are you sure you want to delete "${documentData.title || 'Untitled'}"? This action cannot be undone.`,
      yesButtonText: 'Delete',
      actionKey: 'delete-document'
    };

    this.confirmDialogComponent.show(dialogInfo, () => {
      this.onDeleteDocument?.(documentData.id);
    });
  }

  //==========================================================================||
  //                           Templates and Styles                           ||
  //==========================================================================||
  render() {
    let documentRows = html``;
    for (const documentData of this.documentList) {
      documentRows = html`${documentRows}
        <div
          class="document-row"
          ?is-current=${documentData.id === this.currentDocumentId}
          @click=${() => this.documentClicked(documentData.id)}
        >
          <span class="svg-icon note-icon">${unsafeHTML(noteIcon)}</span>
          <div class="document-info">
            <span class="title">${documentData.title || 'Untitled'}</span>
            <span class="updated-at"
              >${formatUpdatedAt(documentData.updated_at)}</span
            >
          </div>
          <button
            class="delete-button"
            title="Delete"
            @click=${(e: MouseEvent) => this.deleteButtonClicked(e, documentData)}
          >
            <span class="svg-icon">${unsafeHTML(deleteIcon)}</span>
          </button>
        </div>`;
    }

    return html`
      <div class="panel-documents">
        <div class="header">
          <span class="name">My Notes</span>
          <button class="create-button" @click=${() => this.createButtonClicked()}>
            <span class="svg-icon">${unsafeHTML(addIcon)}</span>New Note
          </button>
        </div>

        <div class="document-list">
          ${this.documentListLoading
            ? html`<div class="status-message">Loading your notes…</div>`
            : this.documentList.length === 0
              ? html`<div class="status-message">
                  No notes yet. Everything you write here gets saved
                  automatically.
                </div>`
              : documentRows}
        </div>

        <nightjar-confirm-dialog></nightjar-confirm-dialog>
      </div>
    `;
  }

  static styles = [
    css`
      ${unsafeCSS(componentCSS)}
    `
  ];
}

declare global {
  interface HTMLElementTagNameMap {
    'wordflow-panel-documents': WordflowPanelDocuments;
  }
}
