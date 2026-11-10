/* Minassa — comportements du hub : filtres du catalogue, chemin des parcours,
   formulaire « Prévenez-moi ». Sans dépendance. */
(function () {
  'use strict';

  var APPS_SCRIPT_URL = 'https://script.google.com/macros/s/AKfycbyLIWiRL4jLl5cuLMoyVVNfXkXkCvWPXDHFuRia8gsbn9lGSz3HLxB-bK_s1Mdz-2mq/exec';

  function sansAccents(t) {
    return (t || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
  }

  /* ── Catalogue : filtres Pour / École et recherche ─────────────────── */
  var catalogue = document.querySelector('[data-catalogue]');
  if (catalogue) {
    var lignes = Array.prototype.slice.call(catalogue.querySelectorAll('.ligne-cours'));
    var boutons = Array.prototype.slice.call(catalogue.querySelectorAll('[data-filtre]'));
    var compte = catalogue.querySelector('[data-compte]');
    var vide = catalogue.querySelector('[data-vide]');
    var effacer = Array.prototype.slice.call(document.querySelectorAll('[data-effacer]'));
    var champ = document.getElementById('q');
    var etat = { pour: 'tous', ecole: 'toutes', q: '' };

    var params = new URLSearchParams(window.location.search);
    if (params.get('pour')) etat.pour = params.get('pour');
    if (params.get('ecole')) etat.ecole = params.get('ecole');
    if (params.get('q')) { etat.q = params.get('q'); champ.value = etat.q; }

    var appliquer = function () {
      var mots = sansAccents(etat.q).split(/\s+/).filter(Boolean);
      var n = 0;
      lignes.forEach(function (l) {
        var publics = (l.getAttribute('data-publics') || '').split(' ');
        var ok = (etat.pour === 'tous' || publics.indexOf(etat.pour) >= 0)
          && (etat.ecole === 'toutes' || l.getAttribute('data-ecole') === etat.ecole)
          && mots.every(function (m) { return l.getAttribute('data-texte').indexOf(m) >= 0; });
        l.hidden = !ok;
        if (ok) n++;
      });
      boutons.forEach(function (b) {
        b.setAttribute('aria-pressed', etat[b.getAttribute('data-filtre')] === b.getAttribute('data-valeur') ? 'true' : 'false');
      });
      compte.textContent = n === 0 ? 'Aucun cours' : (n === 1 ? '1 cours' : n + ' cours');
      vide.hidden = n !== 0;
      var filtre = etat.pour !== 'tous' || etat.ecole !== 'toutes' || etat.q !== '';
      effacer[0].hidden = !filtre;

      var p = new URLSearchParams();
      if (etat.pour !== 'tous') p.set('pour', etat.pour);
      if (etat.ecole !== 'toutes') p.set('ecole', etat.ecole);
      if (etat.q) p.set('q', etat.q);
      var qs = p.toString();
      window.history.replaceState(null, '', window.location.pathname + (qs ? '?' + qs : ''));
    };

    boutons.forEach(function (b) {
      b.addEventListener('click', function () {
        etat[b.getAttribute('data-filtre')] = b.getAttribute('data-valeur');
        appliquer();
      });
    });
    champ.addEventListener('input', function () { etat.q = champ.value; appliquer(); });
    effacer.forEach(function (b) {
      b.addEventListener('click', function () {
        etat = { pour: 'tous', ecole: 'toutes', q: '' };
        champ.value = '';
        appliquer();
      });
    });
    appliquer();
  }

  /* ── Apprendre : le chemin des parcours ────────────────────────────── */
  var PARCOURS = {
    M:  { nom: 'Maternelle — J’écoute l’arabe', age: '3–5 ans', chapitres: '20', video: '2 à 3 min', prerequis: 'Aucun', ar: 'اِسْمَعْ', fond: '#F5E1D6', encre: '#B54A1F', sortie: 'reconnaît les 28 lettres à l’oreille et à l’œil, connaît 80 mots et 6 comptines. Il ne lit pas encore.' },
    N1: { nom: 'Niveau 1 — Les lettres', age: '6–7 ans', chapitres: '24', video: '3 à 4 min', prerequis: 'Aucun', ar: 'حُرُوف', sortie: 'lit toutes les lettres dans leurs formes, avec les trois voyelles courtes, et sait les tracer.' },
    N2: { nom: 'Niveau 2 — Je lis', age: '7–8 ans', chapitres: '24', video: '3 à 4 min', prerequis: 'Niveau 1', ar: 'أَقْرَأُ', sortie: 'lit n’importe quel mot vocalisé (voyelles longues, soukoûn, chadda, tanwîn) et copie des mots.' },
    N3: { nom: 'Niveau 3 — Je comprends', age: '8–9 ans', chapitres: '24', video: '4 min', prerequis: 'Niveau 2', ar: 'أَفْهَمُ', sortie: 'lit et comprend des phrases courtes, connaît 300 mots et écrit des mots sous dictée.' },
    N4: { nom: 'Niveau 4 — Je parle', age: '9–10 ans', chapitres: '24', video: '4 à 5 min', prerequis: 'Niveau 3', ar: 'أَتَكَلَّمُ', sortie: 'fait des phrases au présent et au passé, pose des questions, connaît 500 mots, écrit une phrase.' },
    N5: { nom: 'Niveau 5 — Je raconte', age: '10–11 ans', chapitres: '24', video: '4 à 5 min', prerequis: 'Niveau 4', ar: 'أَحْكِي', sortie: 'lit une histoire d’une page et la raconte ; écrit cinq phrases.' },
    N6: { nom: 'Niveau 6 — Ados', age: '12–15 ans', chapitres: '30', video: '5 min', prerequis: 'Niveau 5 ou test', ar: 'أَنَا', fond: '#0B4F4A', encre: '#DCEFEB', sortie: 'parle de son quotidien, lit un texte simple sans voyelles, écrit un paragraphe.' },
    AD: { nom: 'Adulte débutant — De zéro à la lecture et à la conversation', age: '16 ans et +', chapitres: '30', video: '5 à 6 min', prerequis: 'Aucun', ar: 'مَرْحَبًا', fond: '#0B4F4A', encre: '#DCEFEB', sortie: 'lit couramment un texte vocalisé et maîtrise 60 phrases de conversation (niveau A1).' },
    AC: { nom: 'Adulte confirmé — Grammaire, lecture et expression', age: '16 ans et +', chapitres: '30', video: '6 à 7 min', prerequis: 'Adulte débutant ou test', ar: 'نَحْوٌ', fond: '#0B4F4A', encre: '#DCEFEB', sortie: 'connaît la grammaire de base, lit des textes simples sans voyelles et s’exprime par écrit (A2 → B1).' }
  };

  var chemin = document.querySelector('[data-chemin]');
  var choisi = 'N1';
  if (chemin) {
    var choix = Array.prototype.slice.call(chemin.querySelectorAll('[data-parcours]'));
    var champD = function (n) { return chemin.querySelector('[data-d="' + n + '"]'); };
    var bandeau = champD('ar');
    choix.forEach(function (b) {
      b.addEventListener('click', function () {
        choisi = b.getAttribute('data-parcours');
        var p = PARCOURS[choisi];
        choix.forEach(function (x) { x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
        ['nom', 'sortie', 'age', 'chapitres', 'video', 'prerequis', 'ar'].forEach(function (k) { champD(k).textContent = p[k]; });
        bandeau.style.background = p.fond || '#0F766E';
        bandeau.style.color = p.encre || '#F6F1E7';
      });
    });
    var prevenirLien = chemin.querySelector('[data-prevenir]');
    prevenirLien.addEventListener('click', function () {
      var opt = document.querySelector('#p-parcours option[data-parcours="' + choisi + '"]');
      if (opt) opt.selected = true;
      window.setTimeout(function () { document.getElementById('p-email').focus({ preventScroll: true }); }, 400);
    });
  }

  /* ── Formulaire « Prévenez-moi » ───────────────────────────────────── */
  var form = document.getElementById('form-prevenir');
  if (form) {
    var retour = document.getElementById('p-retour');
    var envoyer = document.getElementById('p-envoyer');
    var dire = function (texte, ok) {
      retour.textContent = texte;
      retour.className = 'retour ' + (ok ? 'retour--ok' : 'retour--erreur');
      retour.hidden = false;
    };
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var email = document.getElementById('p-email').value.trim();
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { dire('Indiquez une adresse électronique valide.'); return; }
      if (!document.getElementById('p-consent').checked) { dire('Cochez la case d’accord pour recevoir le courriel.'); return; }
      var jeton = (document.querySelector('[name="cf-turnstile-response"]') || {}).value || '';
      if (document.querySelector('.cf-turnstile') && !jeton) { dire('Validez la vérification anti-robot, puis réessayez.'); return; }

      var parcours = document.getElementById('p-parcours').value;
      var donnees = {
        source: 'parcours',
        type: 'prevenez-moi',
        prenom: document.getElementById('p-prenom').value.trim(),
        nom: '',
        email: email,
        cours: 'Prévenez-moi — ' + parcours,
        message: 'Prévenez-moi à l’ouverture du parcours : ' + parcours,
        _hp: document.getElementById('p-hp').value,
        _turnstile: jeton,
        date: new Date().toLocaleString('fr-FR')
      };
      envoyer.disabled = true;
      fetch(APPS_SCRIPT_URL, {
        method: 'POST', mode: 'no-cors',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(donnees)
      }).then(function () {
        form.reset();
        if (window.turnstile) window.turnstile.reset();
        dire('C’est noté : nous vous écrivons à l’ouverture.', true);
      }).catch(function () {
        dire('L’envoi n’a pas abouti. Réessayez, ou écrivez-nous à contact@minassa.fr.');
      }).then(function () { envoyer.disabled = false; });
    });
  }
})();
