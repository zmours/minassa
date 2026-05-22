// ============================================================
// Online MadrassaNET — Google Apps Script
// Réception des préinscriptions → Google Sheets + Email
// ============================================================
// SETUP :
//  1. Ouvrir https://script.google.com → Nouveau projet
//  2. Coller ce code (remplacer le contenu par défaut)
//  3. Remplacer SHEET_ID par l'ID de votre Google Sheet
//  4. Remplacer NOTIFICATION_EMAIL par votre email
//  5. Déployer : Déployer > Nouveau déploiement
//     - Type : Application web
//     - Exécuter en tant que : Moi
//     - Accès : Tout le monde
//  6. Copier l'URL de déploiement → mettre dans index.html (APPS_SCRIPT_URL)
// ============================================================

const SHEET_ID = 'REMPLACER_PAR_ID_GOOGLE_SHEET'; // ID dans l'URL du sheet
const NOTIFICATION_EMAIL = 'votre@email.com';      // Email qui reçoit les alertes
const SHEET_NAME = 'Préinscriptions';              // Onglet du sheet (créer cet onglet)

// ── En-têtes de colonnes (créées automatiquement à la 1ère soumission) ──
const HEADERS = [
  'Date', 'Prénom', 'Nom', 'Email', 'Téléphone',
  'Pour qui', 'Tranche d\'âge', 'Cours souhaités',
  'Niveau arabe', 'Ville/Pays', 'Message'
];

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);

    // ── Honeypot : si le champ caché "website" est rempli, c'est un bot ──
    if (data._hp && data._hp.length > 0) {
      return ContentService
        .createTextOutput(JSON.stringify({ status: 'success' })) // faux succès
        .setMimeType(ContentService.MimeType.JSON);
    }

    // ── Validation email basique ──
    if (!data.email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)) {
      return ContentService
        .createTextOutput(JSON.stringify({ status: 'error', message: 'Email invalide' }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    // ── Limite : max 5 soumissions par heure depuis la même adresse email ──
    const cache = CacheService.getScriptCache();
    const cacheKey = 'email_' + data.email.toLowerCase().replace(/[^a-z0-9]/g,'_');
    const count = parseInt(cache.get(cacheKey) || '0');
    if (count >= 5) {
      return ContentService
        .createTextOutput(JSON.stringify({ status: 'success' })) // faux succès silencieux
        .setMimeType(ContentService.MimeType.JSON);
    }
    cache.put(cacheKey, String(count + 1), 3600); // expire après 1h

    const sheet = getOrCreateSheet();
    addRowToSheet(sheet, data);
    sendNotificationEmail(data);

    return ContentService
      .createTextOutput(JSON.stringify({ status: 'success' }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    console.error('Erreur doPost:', err.message);
    return ContentService
      .createTextOutput(JSON.stringify({ status: 'error', message: err.message }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

// ── Récupère ou crée l'onglet avec les en-têtes ──
function getOrCreateSheet() {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  let sheet = ss.getSheetByName(SHEET_NAME);

  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
    sheet.appendRow(HEADERS);
    // Mise en forme de l'en-tête
    const headerRange = sheet.getRange(1, 1, 1, HEADERS.length);
    headerRange.setBackground('#1B5E20');
    headerRange.setFontColor('#ffffff');
    headerRange.setFontWeight('bold');
    sheet.setFrozenRows(1);
    sheet.setColumnWidth(1, 160);  // Date
    sheet.setColumnWidth(3, 140);  // Nom
    sheet.setColumnWidth(4, 200);  // Email
    sheet.setColumnWidth(8, 200);  // Cours
    sheet.setColumnWidth(11, 300); // Message
  }

  return sheet;
}

// ── Protège contre l'injection de formules Google Sheets ──
// Un champ commençant par =, +, -, @ peut exécuter du code dans le sheet
function sanitize(value) {
  if (typeof value !== 'string') return value || '';
  const trimmed = value.trim();
  // Préfixe apostrophe : force le texte brut dans Sheets
  if (/^[=+\-@|%]/.test(trimmed)) return "'" + trimmed;
  return trimmed;
}

// ── Ajoute une ligne de données ──
function addRowToSheet(sheet, data) {
  sheet.appendRow([
    data.date        || new Date().toLocaleString('fr-FR'),
    sanitize(data.prenom),
    sanitize(data.nom),
    sanitize(data.email),
    sanitize(data.telephone),
    labelType(data.type),
    labelAge(data.age),
    sanitize(data.cours),
    labelNiveau(data.niveau),
    sanitize(data.ville),
    sanitize(data.message)
  ]);
}

// ── Envoie une notification email ──
function sendNotificationEmail(data) {
  const subject = `🎓 Nouvelle préinscription — ${data.prenom} ${data.nom}`;

  const htmlBody = `
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
      <div style="background:#1B5E20;color:#fff;padding:24px;border-radius:8px 8px 0 0">
        <h2 style="margin:0">🎓 Online MadrassaNET</h2>
        <p style="margin:6px 0 0;opacity:.8">Nouvelle préinscription reçue</p>
      </div>
      <div style="background:#f9f9f9;padding:24px;border:1px solid #e0e0e0">
        <table style="width:100%;border-collapse:collapse">
          <tr><td style="padding:8px;color:#555;width:40%"><strong>Prénom&nbsp;/ Nom</strong></td>
              <td style="padding:8px">${data.prenom} ${data.nom}</td></tr>
          <tr style="background:#fff"><td style="padding:8px;color:#555"><strong>Email</strong></td>
              <td style="padding:8px"><a href="mailto:${data.email}">${data.email}</a></td></tr>
          <tr><td style="padding:8px;color:#555"><strong>Téléphone</strong></td>
              <td style="padding:8px">${data.telephone || '—'}</td></tr>
          <tr style="background:#fff"><td style="padding:8px;color:#555"><strong>Pour qui</strong></td>
              <td style="padding:8px">${labelType(data.type)}</td></tr>
          <tr><td style="padding:8px;color:#555"><strong>Tranche d'âge</strong></td>
              <td style="padding:8px">${labelAge(data.age)}</td></tr>
          <tr style="background:#fff"><td style="padding:8px;color:#555"><strong>Cours souhaités</strong></td>
              <td style="padding:8px"><strong style="color:#1B5E20">${data.cours}</strong></td></tr>
          <tr><td style="padding:8px;color:#555"><strong>Niveau arabe</strong></td>
              <td style="padding:8px">${labelNiveau(data.niveau)}</td></tr>
          <tr style="background:#fff"><td style="padding:8px;color:#555"><strong>Ville / Pays</strong></td>
              <td style="padding:8px">${data.ville || '—'}</td></tr>
          ${data.message ? `<tr><td style="padding:8px;color:#555;vertical-align:top"><strong>Message</strong></td>
              <td style="padding:8px;font-style:italic">${data.message}</td></tr>` : ''}
          <tr style="background:#fff"><td style="padding:8px;color:#555"><strong>Date</strong></td>
              <td style="padding:8px">${data.date}</td></tr>
        </table>
      </div>
      <div style="background:#e8f5e9;padding:16px;border-radius:0 0 8px 8px;text-align:center">
        <a href="https://docs.google.com/spreadsheets/d/${SHEET_ID}" 
           style="color:#1B5E20;font-weight:bold">📊 Voir toutes les préinscriptions →</a>
      </div>
    </div>`;

  MailApp.sendEmail({
    to: NOTIFICATION_EMAIL,
    subject: subject,
    htmlBody: htmlBody
  });
}

// ── Helpers labels ──
function labelType(v) {
  return { enfant: 'Pour mon/mes enfant(s)', adulte: 'Pour moi (adulte)',
           'les-deux': 'Pour moi et mes enfants' }[v] || v || '—';
}
function labelAge(v) {
  return { '5-7': '5 – 7 ans', '8-10': '8 – 10 ans', '11-14': '11 – 14 ans',
           '15-17': '15 – 17 ans', adulte: 'Adulte (18+)',
           plusieurs: 'Plusieurs enfants (âges variés)' }[v] || v || '—';
}
function labelNiveau(v) {
  return { zero: 'Aucune connaissance', alphabet: 'Connaît l\'alphabet',
           lecture: 'Peut lire lentement', intermediaire: 'Niveau intermédiaire',
           avance: 'Niveau avancé' }[v] || v || '—';
}

// ── Test manuel (dans l'éditeur Apps Script, cliquer sur "Exécuter testDoPost") ──
function testDoPost() {
  const fakeEvent = {
    postData: {
      contents: JSON.stringify({
        prenom: 'Fatima', nom: 'Dupont', email: 'test@test.com',
        telephone: '+33600000000', type: 'enfant', age: '8-10',
        cours: 'arabe, coran', niveau: 'zero', ville: 'Paris, France',
        message: 'Test depuis Apps Script', date: new Date().toLocaleString('fr-FR')
      })
    }
  };
  doPost(fakeEvent);
  console.log('Test terminé — vérifiez le sheet et votre email');
}
