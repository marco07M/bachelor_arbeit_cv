"""Split observed name cells with row-individual lexical and syntactic precedence."""

import re
import unicodedata

DEFAULT_ORDER = "family_given"

SURNAME_PARTICLES = frozenset({
    "von", "van", "de", "del", "della", "di", "da", "dos", "das", "du", "des",
    "le", "la", "ten", "ter", "zu", "vom", "zum", "zur", "al", "el", "ben", "ibn", "st", "st.",
})

MULTIWORD_SURNAME_PREFIXES = (
    "von der ", "van der ", "van den ", "van de ", "de la ", "de las ", "de los ",
)

KNOWN_GIVEN_NAMES = frozenset({
    # Classic & modern German / European female given names
    "adele", "adelheid", "agathe", "agnes", "aleksandra", "alessia", "alexa", "alexandra",
    "alice", "alicia", "alina", "aline", "alma", "amelie", "amina", "amira", "amy", "ana",
    "anastasia", "andrea", "aneta", "anett", "anette", "angela", "angelika", "angelina",
    "anika", "anita", "anja", "anke", "ann", "anna", "annabell", "annalena", "anne",
    "annegret", "anneliese", "annemarie", "annette", "anni", "annika", "antje", "antonia",
    "ariane", "astrid", "aurelia", "aylin", "ayse", "ayşe", "barbara", "beata", "beate",
    "beatrice", "beatrix", "belinda", "berenike", "bernadette", "berta", "bertha", "bettina",
    "bianca", "bianka", "birgit", "birte", "birthe", "brigitte", "britta", "camilla", "carina",
    "carla", "carmen", "carola", "carolin", "carolina", "caroline", "catarina", "catharina",
    "catherine", "celina", "celine", "chantal", "charleen", "charlotte", "chiara", "christa",
    "christel", "christiana", "christiane", "christina", "christine", "cindy", "claire",
    "clara", "clarissa", "claudia", "constanze", "cordula", "corinna", "cornelia", "cosima",
    "dagmar", "dana", "daniela", "daria", "debora", "deborah", "delia", "denise", "desiree",
    "diana", "dilara", "doerte", "dora", "ulrike", "doreen", "doris", "dorothea", "dorothee",
    "dörte", "edeltraud", "edith", "aksinya", "elena", "eleonore", "elfriede", "eliana",
    "elif", "elina", "elisa", "elisabeth", "elise", "ella", "ellen", "elli", "elly", "elsa",
    "else", "elvira", "emanuela", "emely", "emilia", "emilie", "emily", "emma", "emine",
    "emmy", "enisa", "erika", "erna", "esra", "esther", "eva", "evelin", "evelyn", "fabienne",
    "fatima", "fatma", "felicitas", "fenja", "finja", "fiona", "flora", "florentine",
    "francesca", "franka", "franziska", "frauke", "frederike", "freya", "frida", "frieda",
    "friederike", "gabi", "gabriele", "gaby", "gerda", "gerlinde", "gertrud", "gesa", "gesine",
    "gina", "gisela", "gitta", "greta", "gretchen", "grete", "gudrun", "gunda", "gundula",
    "halina", "hanna", "hannah", "hanne", "hannelore", "hatice", "hedda", "hedwig", "hedy",
    "heide", "heidemarie", "heidi", "heike", "helen", "helena", "helene", "helga", "hella",
    "helma", "henriette", "henrike", "herta", "hertha", "hilda", "hilde", "hildegard", "hulda",
    "ida", "ilka", "ilona", "ilse", "imke", "ina", "ines", "inga", "inge", "ingeborg",
    "ingrid", "inka", "irena", "irene", "uetta", "iris", "irma", "irmgard", "isabel",
    "isabell", "isabella", "isabelle", "ivana", "ivonne", "jacqueline", "jana", "janet",
    "janina", "janine", "janna", "jasmin", "jasmine", "jeanette", "jeannette", "jelena",
    "jennifer", "jenny", "jessica", "jette", "jil", "jill", "joana", "johanna", "jolanta",
    "josefine", "josephine", "josi", "judith", "jule", "julia", "juliana", "juliane", "julie",
    "justine", "jutta", "karen", "karin", "karina", "karla", "karolina", "karoline",
    "kassandra", "kata", "katarina", "katarzyna", "katharina", "käthe", "katrin", "katja",
    "katinka", "kerstin", "kim", "kira", "kirsten", "kirstin", "klara", "kornelia", "kristin",
    "kristina", "kristine", "lara", "larissa", "laura", "laureen", "lea", "leah", "leila",
    "lena", "leni", "leonie", "leonora", "leyla", "lia", "liane", "lidia", "lieselotte",
    "lili", "liliana", "lilli", "lilly", "lina", "linda", "linnea", "lisa", "lisbeth", "lissy",
    "liv", "livia", "lore", "loren", "lotte", "louisa", "louise", "lucia", "lucie", "luisa",
    "luise", "luna", "luzia", "lydia", "lynn", "madeleine", "madlen", "magda", "magdalena",
    "magdalene", "maike", "maja", "malgorzata", "malin", "mandy", "manja", "manuela", "mara",
    "mareike", "marek", "maren", "margarete", "margarethe", "margit", "margot", "margret",
    "margrit", "maria", "mariam", "marianna", "marianne", "marie", "marietta", "marika",
    "marina", "marion", "marisa", "marit", "marita", "maritta", "marjan", "marleen", "marlen",
    "marlene", "marlies", "marliese", "marlis", "marta", "martha", "martina", "mathilde",
    "matilda", "maya", "mechthild", "meike", "melanie", "melina", "melinda", "melisa",
    "melissa", "merle", "merve", "meta", "mia", "michaela", "michelle", "mila", "milena",
    "mina", "mira", "miriam", "mirjam", "mona", "monika", "monique", "nadine", "nadja",
    "nanette", "naomi", "natalia", "natalie", "natascha", "nathalie", "nee", "nele", "nelly",
    "nicole", "nina", "noemi", "nora", "olga", "olivia", "oriana", "oxana", "pamela",
    "patricia", "patrizia", "paula", "pauline", "peggy", "petra", "philippa", "pia",
    "priska", "rabea", "rachel", "rahel", "ramona", "raphaela", "rebecca", "rebekka",
    "regina", "regine", "renate", "ria", "ricarda", "rita", "romina", "romy", "ronja", "rosa",
    "rosalie", "rosamunde", "rose", "rosemarie", "witha", "roswitha", "ruth", "sabine",
    "sabrina", "sahra", "sally", "salome", "samira", "sandra", "sandy", "sanja", "sara",
    "sarah", "saskia", "selina", "selma", "serap", "sevda", "sibylle", "sieglinde", "sigrid",
    "sigrun", "silke", "silvana", "silvia", "simona", "simone", "sina", "sinah", "smilla",
    "sofia", "sofie", "sonja", "sonya", "sophia", "sophie", "stefanie", "steffi", "stella",
    "stephanie", "svea", "svenja", "svetlana", "swetlana", "sybille", "sylke", "sylvia",
    "tabea", "tamara", "ania", "tanja", "tatjana", "teresa", "tessa", "thea", "theresa",
    "therese", "tina", "traute", "ulrike", "ursel", "ursula", "uta", "ute", "valENTINA",
    "valentina", "valerie", "vanessa", "vera", "verena", "veronika", "victoria", "viktoria",
    "viola", "vivian", "vivien", "walburga", "waltraud", "wanda", "wiebke", "wilhelmine",
    "wilma", "xenia", "yasmin", "yvonne", "zeynep", "zoe", "zoë", "zuzana",
    # Classic & modern German / European / international male given names
    "aaron", "abbas", "abdul", "abdullah", "achim", "adalbert", "adam", "adnan", "adolf",
    "adrian", "ahmad", "ahmed", "ahmet", "alain", "alan", "albert", "albin", "albrecht",
    "aleksandar", "aleksander", "alessandro", "alex", "alexander", "alexej", "alexis",
    "alfons", "alfred", "ali", "alois", "alwin", "amadeus", "amir", "anatoli", "anatolij",
    "andre", "andré", "andreas", "andrej", "andreas", "andrew", "andrzej", "andy", "ansgar",
    "ante", "anthony", "anton", "antonio", "antonius", "armin", "arnd", "arndt", "arne",
    "arno", "arnold", "arnulf", "artur", "arthur", "attila", "august", "aurel", "axel",
    "aykut", "bahadir", "bastian", "ben", "benedikt", "benjamin", "bennet", "benno", "bernd",
    "bernhard", "bert", "berthold", "bertram", "bilal", "bjarne", "bjoern", "björn", "odo",
    "bodo", "bogdan", "boris", "branko", "brian", "bruno", "burkhard", "burkhart", "can",
    "carl", "carlos", "carsten", "cedric", "cem", "cevdet", "charles", "chris", "christian",
    "christof", "christoph", "christopher", "claas", "claus", "clemens", "colin", "conrad",
    "constantin", "cord", "cornelius", "cosimo", "curd", "cyrill", "damian", "damir", "dan",
    "daniel", "danilo", "danny", "dario", "dariusz", "darko", "david", "davide", "dejan",
    "denis", "dennis", "detlef", "detlev", "didi", "dieter", "diethelm", "dietmar", "dietrich",
    "dimitri", "dimitrij", "dino", "dirk", "dmitri", "dominic", "dominik", "dominique",
    "donald", "dorian", "dragan", "dušan", "dusan", "dustin", "eberhard", "eckart", "eckhard",
    "edgar", "edmund", "eduard", "edward", "edwin", "egbert", "egon", "ehrenfried", "eike",
    "ekkehard", "elias", "elmar", "emanuel", "emil", "emilio", "emir", "emre", "enes",
    "enno", "enrico", "erdal", "erdogan", "erhard", "eric", "erich", "erik", "ernest",
    "ernst", "erwin", "etienne", "eugen", "ewald", "fabian", "fabio", "falk", "falko",
    "faruk", "fatih", "fedor", "felix", "ferdinand", "ferhat", "fideli", "fiete", "filip",
    "finn", "florian", "frank", "franz", "fred", "freddy", "frederic", "frederik", "fredi",
    "friedhelm", "friedolin", "friedrich", "fritz", "fynn", "gabriel", "geert", "georg",
    "george", "gerald", "gerd", "gerhard", "gerhart", "german", "gernot", "gero", "gerold",
    "gerrit", "gert", "gilbert", "gino", "giovanni", "gisbert", "giuseppe", "goran",
    "gottfried", "gotthard", "gottlieb", "gregor", "grzegorz", "guenter", "guenther", "guido",
    "gunnar", "gunter", "gunther", "gustav", "günther", "günter", "hakan", "halil", "hamid",
    "hamza", "hannes", "hanno", "hanns", "hans", "harald", "hardy", "harri", "harry",
    "hartmut", "hartwig", "hasan", "hassan", "hauke", "heiko", "heiner", "heino", "heinrich",
    "heinz", "helge", "hellmut", "hellmuth", "helmut", "helmuth", "hendrik", "henning",
    "henri", "henrik", "henry", "herbert", "heribert", "hermann", "herwig", "hilmar",
    "hinrich", "holger", "horst", "hubert", "hubertus", "hugo", "hüseyin", "ibrahim",
    "ignaz", "igor", "ilhan", "ilias", "ilja", "immanuel", "ingo", "ingolf", "ingomar",
    "isaak", "ismail", "ivan", "ivo", "iwan", "jacek", "jack", "jacob", "jakob", "jamal",
    "james", "jan", "janek", "janis", "jannik", "jannis", "janosch", "jarek", "jaroslaw",
    "jason", "jasper", "jay", "jean", "jens", "jeremias", "jerome", "jerzy", "jesko",
    "joachim", "jobst", "jochen", "joel", "joerg", "jörg", "johann", "johannes", "john",
    "jonah", "jonas", "jonathan", "jorge", "joris", "jose", "josef", "joseph", "josip",
    "josua", "juan", "julian", "julius", "jürgen", "juergen", "juri", "jurij", "justin",
    "justus", "kaan", "kai", "kajetan", "kalle", "kamil", "karim", "karl", "karlheinz",
    "karsten", "kasimir", "kaspar", "kay", "kazim", "kemal", "kenan", "kenneth", "kevin",
    "khalid", "kian", "kilian", "kim", "kjell", "klaas", "klaus", "klemens", "knut",
    "konrad", "konstantin", "korbinian", "kornelius", "krunoslav", "krzysztof", "kuno",
    "kurt", "lambert", "lars", "lasse", "laurenz", "leander", "leif", "lennard", "lennart",
    "lenny", "leo", "leon", "leonard", "leonardo", "leonhard", "leonid", "leopold", "levin",
    "liam", "linus", "lionel", "lorenz", "lothar", "louis", "luca", "lucas", "ludger",
    "ludwig", "luis", "luka", "lukas", "lukasz", "lutz", "maik", "malte", "manfred",
    "manuel", "marc", "marcel", "marco", "marcus", "marek", "marian", "mario", "marius",
    "mariusz", "mark", "marko", "markus", "marlon", "marten", "martin", "marvin", "marwin",
    "matej", "mateo", "matheo", "mathias", "mathis", "mats", "matteo", "matthäus",
    "matthias", "matthieu", "matti", "mattis", "maurice", "max", "maxim", "maximilian",
    "mehdi", "mehmet", "meik", "meinhard", "melvin", "mesut", "metin", "michael", "michal",
    "michel", "mick", "miguel", "mika", "mike", "mikhail", "milan", "milo", "milos",
    "mirco", "mirko", "miroslav", "miroslaw", "mitch", "mohamed", "mohammad", "mohammed",
    "moritz", "muhamed", "muhammed", "murat", "mustafa", "nabil", "nadim", "nathan",
    "necati", "nelio", "nelson", "nenad", "neven", "nick", "nico", "nicolai", "nicolas",
    "nicolaus", "niels", "nikita", "niklas", "niko", "nikola", "nikolai", "nikolaj",
    "nikolas", "nikolaus", "nils", "noah", "noel", "norbert", "norman", "nuri", "olaf",
    "ole", "oleg", "oliver", "omar", "onur", "orhan", "orlando", "oscar", "oskar", "osman",
    "oswald", "otmar", "ottmar", "otto", "ove", "ömer", "özcan", "özgür", "pablo", "pascal",
    "patric", "patrick", "patrik", "paul", "paolo", "pavel", "pawel", "pedro", "peer",
    "per", "pero", "peter", "petros", "phil", "philip", "philipp", "philippe", "phillip",
    "pierre", "piotr", "pius", "quentin", "quinten", "quirin", "rachid", "radek", "radomir",
    "rafael", "raimund", "rainer", "ralf", "ralph", "ramazan", "ramon", "randolf", "raphael",
    "rasmus", "raul", "raymond", "recep", "reimar", "reimund", "reiner", "reinhard",
    "reinhart", "reinhold", "remigius", "remo", "rene", "rené", "reto", "ricardo", "richard",
    "rico", "rijad", "rino", "robert", "roberto", "robin", "rocco", "roch", "roderich",
    "roger", "roland", "rolf", "roman", "romeo", "ron", "ronald", "ronny", "rouven", "roy",
    "ruben", "rudi", "rudolf", "rudolph", "rupert", "ruppert", "rüdiger", "ruediger",
    "salih", "sam", "sami", "samir", "samuel", "sandro", "sascha", "sebastian", "selim",
    "semih", "sepp", "serdar", "sergei", "sergej", "sergio", "severin", "siegbert",
    "siegfried", "sieghard", "siegmar", "siegmund", "sigmar", "sigmund", "silas", "silvio",
    "simon", "sinan", "slaven", "slobodan", "sören", "soeren", "stanislaw", "stanley",
    "stefan", "steffen", "stephan", "stephen", "steve", "steven", "stjepan", "sven", "swen",
    "sylvester", "sylvio", "tadeus", "tadeusz", "tahir", "tarek", "tarik", "tayfun", "theo",
    "theodor", "thiemo", "thies", "thilo", "thomas", "thorben", "thorsten", "tibor", "till",
    "tillmann", "tilman", "tilo", "tim", "imm", "timo", "timon", "timotheus", "timur",
    "tino", "titus", "tobias", "tom", "tomas", "tomasz", "tomislav", "tommy", "toni",
    "tony", "torben", "torge", "torsten", "tristan", "udo", "ufuk", "ulrich", "ulrich",
    "uwe", "vadim", "valentin", "valerij", "veit", "veljko", "victor", "viktor", "vincent",
    "vinzenz", "vitali", "vitalij", "vito", "vladimir", "volkan", "volker", "volkmar",
    "waldemar", "walter", "walther", "wassili", "wenzel", "werner", "wido", "wiegand",
    "wieland", "wilfried", "wilhelm", "willi", "william", "willy", "wim", "winfried",
    "witold", "wladimir", "wojciech", "wolf", "wolfgang", "wolfram", "wulf", "xaver",
    "yannic", "yannick", "yannik", "yasin", "yavuz", "yilmaz", "yunus", "yusuf", "yves",
    "zdravko", "zeki", "zlatko", "zoran", "zsolt",
})

PURE_SURNAMES = frozenset({
    "achtermann", "ackermann", "adler", "ahrens", "albers", "albrecht", "altmann", "ammann",
    "anders", "andresen", "appel", "arendt", "armbruster", "arndt", "aschauer", "auer",
    "bach", "bacher", "bachmann", "backhaus", "bader", "baier", "baldauf", "bartels",
    "barth", "barthel", "bartsch", "bauer", "bauersfeld", "baum", "baumann", "baumbach",
    "baumgart", "baumgartner", "baumgärtner", "baur", "bayer", "becher", "ulrich", "beck",
    "becker", "beckers", "beckmann", "beer", "behrend", "behrendt", "behrens", "beier",
    "beispiel", "bender", "benkert", "benz", "berg", "berger", "bergmann", "berndt",
    "bernhardt", "bertram", "betz", "beyer", "binder", "birken", "bischoff", "ach",
    "bittner", "blank", "blume", "bock", "bode", "boehm", "boehme", "boettcher", "bogner",
    "bohlen", "bollmann", "bonk", "borchert", "borgmann", "bormann", "born", "borowski",
    "uhlmann", "brand", "brandl", "brandt", "brauer", "braun", "braune", "brehm", "breier",
    "breit", "bremer", "brenner", "breuer", "brink", "brinkmann", "brockmann", "brodbeck",
    "brugger", "oid", "brunner", "bruns", "bucher", "buchholz", "buchmann", "buck",
    "buehler", "buettner", "bühler", "büttner", "burchardt", "burg", "burger", "burghardt",
    "burkhardt", "busch", "buschmann", "buse", "busse", "böhm", "böhme", "böttcher",
    "carstens", "christ", "christensen", "clausen", "conrad", "cordes", "cremer", "czerny",
    "dahmen", "damm", "dammann", "dann", "debus", "deck", "decker", "degen", "dehn",
    "delbrück", "demuth", "denk", "detering", "dewald", "dick", "diehl", "dierks",
    "dietrich", "dietz", "dietze", "dill", "dittmann", "dittmar", "dittrich", "dobler",
    "doering", "doerr", "dohmen", "doll", "dombrowski", "donath", "dorn", "dorner",
    "dorsch", "drechsler", "dreher", "dreier", "dressler", "drews", "dreyer", "droste",
    "döring", "dörr", "ebeling", "eberhardt", "eberl", "eberle", "ebert", "ebner", "eck",
    "eckert", "eckhardt", "edelmann", "eder", "eggers", "eggert", "ehlert", "ehmann",
    "ehret", "ehrlich", "eich", "eichel", "eichhorn", "eichler", "eichmann", "eickhoff",
    "eilers", "eisner", "eller", "elsner", "emmerich", "engel", "engelbrecht", "engels",
    "erdmann", "erhardt", "ertl", "esch", "escher", "esser", "evers", "ewald", "exner",
    "faber", "falk", "falke", "fassbender", "faust", "fechner", "fehrenbach", "feige",
    "feld", "feldmann", "feller", "fellner", "ferber", "fichtner", "fiedler", "fink",
    "finke", "fischer", "fleischer", "fleischmann", "flemming", "flick", "flohr",
    "foerster", "folgeseite", "forster", "franke", "franzke", "freitag", "frenz", "frenzel",
    "frese", "freund", "frey", "freyer", "freytag", "frick", "fricke", "friedel", "friedl",
    "friedmann", "friedrichs", "fries", "friese", "fritsch", "fritsche", "fritzsche",
    "froehlich", "fromm", "fröhlich", "fuchs", "fuehrer", "fuhr", "fuhrmann", "funke",
    "fürst", "förster", "gabel", "gaertner", "gaiser", "gall", "ganser", "garbe", "gassert",
    "gast", "gebauer", "gebhardt", "gehring", "gehrke", "geier", "geiger", "geis", "geisler",
    "geissler", "geißler", "geller", "gensler", "gentner", "gerber", "gerdes", "gerhardt",
    "gerlach", "germany", "gerner", "gerstner", "geyer", "giese", "gieseke", "giesen",
    "glaser", "glas", "glatz", "gleich", "gleissner", "glock", "glöckner", "goebel",
    "goerlich", "goertz", "goetz", "goetze", "gold", "goldbach", "goldberg", "goldmann",
    "golomb", "golz", "gottwald", "grabowski", "gradl", "graf", "gramlich", "grau", "grebe",
    "greiner", "greve", "griebel", "griess", "grimm", "groeger", "groh", "grohmann", "groll",
    "gronau", "gross", "grosse", "grossmann", "groth", "grothe", "groß", "große", "großmann",
    "grube", "gruber", "gruen", "gruenewald", "grund", "grundmann", "gruner", "grunert",
    "grunwald", "grün", "grünewald", "gröger", "guenther", "gundlach", "gutmann", "gutsch",
    "guttmann", "gärtner", "göbel", "görlich", "görtz", "götz", "götze", "haack", "haag",
    "haake", "haas", "haase", "abel", "habermann", "hack", "hacker", "hackl", "haefner",
    "haendel", "haering", "haertel", "haertl", "hafen", "hagedorn", "hagemann", "hagen",
    "hager", "hahn", "hahne", "haider", "hain", "halbritter", "haller", "hamann", "hamm",
    "hammer", "hammerschmidt", "hampe", "hampel", "handke", "handschrift", "hanke", "hannemann",
    "hansen", "hansmann", "harms", "harnisch", "arrer", "hartig", "hartl", "hartmann",
    "hartung", "hartwig", "hasel", "hass", "hasse", "atz", "hauck", "hauff", "haug",
    "hauke", "haupt", "hauptmann", "haus", "hauser", "hausmann", "haussmann", "hecht",
    "heck", "hecker", "heckmann", "hedrich", "heer", "heger", "heide", "heidemann",
    "heiden", "heidenreich", "heider", "heiland", "heil", "heilmann", "heim", "heimann",
    "hein", "heine", "heinemann", "heinen", "heinicke", "heinrichs", "heins", "ock",
    "heintz", "heinze", "heise", "heiss", "heiß", "held", "hell", "heller", "hellmann",
    "hellwig", "helm", "helmer", "helmich", "hemmer", "hempel", "henke", "henkel", "henn",
    "henne", "hennecke", "hennig", "henning", "hennings", "henrich", "henschel", "hensel",
    "henze", "hepp", "hepper", "herbst", "herd", "herder", "herget", "hering", "ermann",
    "hermes", "herold", "herr", "herrmann", "hertel", "herter", "hertwig", "hertz", "herz",
    "herzberg", "herzig", "herzog", "hess", "hesse", "heß", "hettich", "hetzel", "heuer",
    "heumann", "hey", "heyd", "heyde", "heyer", "heymann", "hielscher", "hierl", "hilbert",
    "hild", "hildebrand", "hildebrandt", "hildenbrand", "hilger", "hill", "hille",
    "hillebrand", "hiller", "hillmann", "himmel", "hinrichs", "hintz", "hintze", "hinz",
    "hinze", "hirsch", "hirschmann", "hirt", "hoch", "hock", "hoefler", "hoefner", "hoehne",
    "hoeller", "hoelzl", "hoenig", "hoeppner", "hoerner", "hoevel", "hof", "ofbauer",
    "hofer", "hoff", "hoffmann", "hoffmeister", "hofmann", "hofmeister", "hohmann", "huber",
    "hold", "holder", "holl", "holland", "holler", "hollmann", "holst", "holtmann", "holtz",
    "holz", "holzapfel", "holzer", "holzmann", "homann", "hommel", "honecker", "honig",
    "hopf", "hoppe", "horn", "hornung", "reuter", "horstmann", "hotz", "hoyer", "huber",
    "hubert", "huck", "huebner", "huebsch", "huegel", "huels", "huelsmann", "huetter",
    "hufnagel", "huh", "huhn", "hummel", "hundt", "hunger", "husemann", "husmann", "huth",
    "hübner", "hübsch", "hügel", "hüls", "hülsmann", "hütter", "häfner", "händel", "häring",
    "härtel", "härtl", "höfler", "höfner", "höhne", "höller", "hölzl", "hönig", "höppner",
    "hörner", "ihle", "ilg", "imhof", "immel", "irmer", "isermann", "jacobi", "jacobs",
    "jacobsen", "jaeger", "jaehn", "jaensch", "jahn", "jahnke", "jahns", "jakobi", "jakobs",
    "janke", "jansen", "janson", "janssen", "janßen", "janz", "janzen", "jauch", "jensen",
    "jentsch", "jeschke", "jessen", "joachim", "jochim", "jochum", "john", "johne",
    "johnson", "jonas", "jordan", "jost", "josten", "jung", "junge", "jungghans", "junghans",
    "jungmann", "junker", "jürgens", "jürgensen", "jäger", "jähn", "jänsch", "kaehler",
    "kaemmerer", "kaestner", "kahl", "kahle", "kahlert", "kaiser", "kalb", "kallenbach",
    "kaltenbach", "kammer", "kammerer", "kamp", "kampe", "kampmann", "kanz", "kanzler",
    "kapp", "kappel", "kappes", "kappler", "karcher", "karg", "karger", "karlsson", "karpf",
    "karrasch", "karsten", "kasper", "kassel", "kast", "kasten", "kastl", "kastner", "katz",
    "kaufmann", "kaul", "kausch", "kautz", "kayser", "keck", "kegel", "kehl", "kaiser",
    "kehrer", "keil", "keim", "keller", "kellermann", "kellner", "kempe", "kemper", "kempf",
    "keppler", "kerber", "kerl", "kern", "kerner", "kersten", "kessel", "kessler", "keßler",
    "kettler", "kettner", "keutel", "kick", "kiefer", "kiel", "kienle", "kienzle",
    "kiesewetter", "kiesling", "kiessling", "kießling", "kilian", "kind", "kinder",
    "kindermann", "kindler", "kinzel", "kipp", "kirch", "kirchhoff", "kirchner", "kirsch",
    "kirschbaum", "kirschner", "kirst", "kirstein", "kirsten", "kissling", "kittel",
    "klages", "klapproth", "klar", "klas", "klasen", "att", "klatt", "klauser", "kleber",
    "klee", "kleemann", "klein", "kleine", "kleiner", "kleinert", "kleinhans", "kleinschmidt",
    "kleist", "klemm", "klenk", "klement", "klinger", "kling", "klinge", "klingel",
    "klingenberg", "klinger", "klingler", "klink", "klinke", "klinkhammer", "klocke",
    "kloos", "klose", "klostermann", "klotz", "klug", "kluge", "klumb", "kluth", "knaack",
    "knabe", "knapp", "knappe", "knauer", "knauf", "knaus", "knebel", "knecht", "kneip",
    "knittel", "knobloch", "knoch", "knoche", "knoell", "knoll", "knop", "knopf", "knopp",
    "knorr", "knuth", "kober", "koch", "kock", "koehler", "koehn", "koeller", "koenig",
    "koepke", "koeppe", "koeppen", "koerber", "koerner", "koester", "koesters", "kohl",
    "kohler", "kohlmann", "kohn", "kohout", "kolb", "kolbe", "koller", "kollmann", "konietzny",
    "konrad", "koop", "koopmann", "kopf", "kopp", "koppe", "koppel", "korb", "korn",
    "kort", "korte", "korth", "koslowski", "koss", "kost", "kothe", "kotz", "kowalski",
    "kowalczyk", "kraemer", "kraft", "krah", "krahn", "kramer", "kramm", "kramp", "kranz",
    "krapf", "kratz", "kratzer", "kraus", "krause", "krauss", "krauß", "krawczyk", "krebs",
    "kreft", "kreil", "kreiner", "kreis", "kreisel", "kremer", "kremser", "krenz", "kress",
    "kreß", "kretschmann", "kretschmer", "kretz", "kretzschmar", "kreuz", "kreuzer",
    "krey", "krieg", "krieger", "klinger", "krings", "kroeger", "kroener", "krohn", "kroll",
    "kromer", "krone", "kropf", "krug", "krueger", "krull", "krumm", "krupa", "kruppa",
    "kruse", "krämer", "kröger", "kröner", "krüger", "kube", "kuch", "kuchenbecker",
    "kuck", "kuechler", "kuehl", "kuehn", "kuehne", "kuehnel", "kuehner", "kuemmel",
    "kuenast", "kuenzel", "kuester", "kugel", "kugler", "kuhl", "kuhlmann", "kuhn", "kuhnert",
    "kuhnt", "kulik", "kullmann", "kummer", "kunath", "kunde", "kunert", "kunkel", "kunst",
    "kuntz", "kuntze", "kunz", "kunze", "kupfer", "kupka", "kurth", "kurtz", "kurz",
    "kusch", "kuschel", "kutscher", "kutz", "utzner", "kähler", "kämmerer", "kästner",
    "köhler", "köhn", "köller", "könig", "köpke", "köppe", "köppen", "körber", "körner",
    "köster", "kösters", "küchler", "kühl", "kühn", "kühne", "kühnel", "kühner", "kümmel",
    "künzel", "küster", "lachmann", "lackner", "ladwig", "laemmel", "laemmer", "lahm",
    "lamm", "lammers", "lampe", "lamprecht", "landau", "landgraf", "landmann", "landwehr",
    "lang", "lange", "langer", "langanki", "langbein", "langen", "langguth", "langhammer",
    "langhans", "langhoff", "langner", "lanz", "laskowski", "lau", "laube", "lauber",
    "laue", "lauer", "laufer", "laumann", "lauterbach", "laux", "leber", "lechner",
    "leder", "lederer", "leeb", "lehmann", "lehner", "lehnert", "lehr", "leibold", "leicht",
    "lein", "leipold", "leis", "leiser", "leistner", "leitner", "lell", "lemke", "lemm",
    "lemmer", "lenk", "lennartz", "lensch", "lentz", "lenz", "lenzen", "leonhardt", "lepp",
    "lerch", "lesch", "lessing", "lettner", "leuschner", "leutner", "lewandowski", "lex",
    "ley", "licht", "lichtenberger", "lichtenstein", "liebig", "liebl", "liebmann", "liedtke",
    "liemann", "lienhard", "lieske", "lietz", "limbach", "limmer", "linck", "lind",
    "linde", "lindemann", "linden", "lindenberg", "linder", "lindner", "ling", "link",
    "linke", "linn", "linnemann", "lins", "linse", "lippert", "lipp", "lippmann", "lips",
    "list", "loch", "locher", "loeffler", "loehr", "loercher", "loesch", "loeser", "loew",
    "loewe", "lohmann", "lohr", "lohse", "loos", "loose", "lorenzen", "losch", "lotz",
    "lotze", "lucas", "lucht", "lucke", "ludewig", "ludwig", "luebke", "lueck", "luedecke",
    "lueders", "luehr", "luetke", "luettich", "luft", "lutter", "lutz", "lutze", "lämmel",
    "lämmer", "löffler", "löhr", "lörcher", "lösch", "löser", "löw", "löwe", "lübke",
    "lück", "lüdecke", "lüders", "lühr", "lütke", "maack", "maas", "maass", "maaß", "mach",
    "mache", "machnik", "mack", "mader", "maehler", "maerz", "magin", "mahler", "mahn",
    "mahnke", "mai", "maier", "maiwold", "maiwald", "majewski", "malinowski", "malkowski",
    "mall", "malz", "mandel", "mang", "mangold", "anke", "mann", "manns", "manthey",
    "manz", "marquardt", "marschall", "marschner", "martens", "martini", "marx", "maschke",
    "mast", "materna", "mathes", "mathis", "mattern", "mattes", "matthes", "matthiesen",
    "matz", "matzke", "mau", "mauch", "mauer", "maurer", "maus", "may", "mayer", "mayr",
    "meder", "mehl", "mehler", "mehlhorn", "mehnert", "meier", "meinert", "meinhardt",
    "meinke", "meisel", "meissner", "meißner", "meister", "melcher", "melchers", "melzer",
    "menke", "menne", "mensch", "mentzel", "menzel", "merkel", "merker", "merkl", "merk",
    "mertens", "mertes", "mertz", "merz", "meschke", "messer", "messerschmidt", "messner",
    "metz", "metzger", "metzler", "metzner", "meurer", "meusel", "mewes", "mey", "meyer",
    "michaelis", "michalski", "michel", "michels", "mielke", "milde", "milz", "mink",
    "mischke", "mittermayer", "mittermeier", "och", "mock", "moehle", "moeller", "moench",
    "moerz", "mohr", "moldenhauer", "moll", "molter", "mommsen", "mond", "morgen",
    "morgenroth", "morgenstern", "moser", "motz", "muck", "mueck", "muehl", "muehlbauer",
    "muehle", "muehlhausen", "mueller", "muench", "muenster", "muenze", "mues", "mütze",
    "möhle", "möller", "mönch", "mück", "mühl", "mühlbauer", "mühle", "mühlhausen",
    "müller", "münch", "münster", "münze", "nachtigall", "nachtrag", "ack", "nadler",
    "nagel", "nagle", "nagler", "opfer", "nau", "naujoks", "naumann", "nebel", "necker",
    "neef", "neff", "nehls", "nehring", "neidel", "neidhardt", "neininger", "nelson",
    "nemeth", "nessel", "nestler", "nett", "neu", "neubauer", "neubert", "neuburger",
    "neudorfer", "neuenfeldt", "neuer", "neufeld", "neugebauer", "neuhaus", "neuhäuser",
    "neumaier", "neumann", "neumeier", "neumeister", "neumüller", "neuner", "ney", "nickel",
    "nickl", "niebuhr", "nieder", "niedermeier", "niedermeyer", "niehaus", "ust", "niemann",
    "niemeyer", "nienhaus", "niermann", "nies", "niessen", "nießen", "niggel", "niklas",
    "nikolaus", "nissen", "nitz", "nitzsche", "noack", "nold", "nolde", "noll", "nolte",
    "nolting", "nordmann", "nowak", "nowotny", "nussbaum", "nußbaum", "nürnberger", "ober",
    "oberländer", "obermaier", "obermeier", "obermeyer", "obst", "ochs", "oehler", "oehm",
    "oehme", "oelkers", "oertel", "oesterle", "oesterreich", "oestreich", "offermann",
    "ohle", "ohlendorf", "ohlsen", "ohm", "olbrich", "oldenburg", "olschewski", "opitz",
    "oppelt", "oppenheimer", "oppermann", "ortega", "orth", "ortlieb", "ortmann", "ortner",
    "ostendorf", "oster", "ostermann", "ostertag", "ostwald", "ott", "otte", "otten",
    "ottmann", "overbeck", "pabst", "pahl", "pahlke", "palm", "panzer", "pape", "papke",
    "paschke", "patzer", "pauli", "paulsen", "paulus", "pawlowski", "pech", "peil",
    "peinemann", "pelz", "pelzer", "penner", "peschel", "peschke", "peter", "petermann",
    "peters", "petersen", "petri", "petry", "petzold", "peukert", "pfaff", "pfannenstiel",
    "pfau", "pfeffer", "pfeifer", "pfeiffer", "pfeil", "pfister", "pfisterer", "pfitzner",
    "pflueger", "pflug", "pflüger", "pohl", "philippi", "philipps", "pichler", "pick",
    "pickel", "pieper", "pietsch", "pilz", "pinkert", "pinto", "piontek", "pitz", "plank",
    "plate", "plath", "platz", "plötz", "pohl", "pohle", "pohlmann", "polak", "pollak",
    "pollmann", "polster", "polzin", "pommer", "popp", "poppe", "porst", "posch", "posselt",
    "post", "poth", "pott", "potthoff", "prahl", "prager", "prange", "preiss", "preiß",
    "prell", "preuss", "preuß", "priebe", "pries", "prinz", "probst", "prochnow", "prokisch",
    "propst", "prüfer", "pröhl", "puchta", "pütz", "pöhlmann", "pötzsch", "quack", "quandt",
    "quast", "quell", "quabeck", "raab", "raabe", "rabe", "rack", "rademacher", "radke",
    "radloff", "radtke", "raeder", "rahn", "aiser", "ramm", "rand", "ranft", "rank",
    "ranke", "rapp", "rasch", "rasche", "raschke", "rath", "ratz", "rau", "rauch", "rauh",
    "raupach", "rausch", "rauscher", "rautenberg", "reber", "rech", "reck", "recker",
    "redeker", "redlich", "reese", "regele", "regen", "reger", "reh", "rehberg", "rehm",
    "reich", "reichardt", "reiche", "reichel", "reichelt", "reichenbach", "ufers", "reichert",
    "reichl", "reichmann", "reif", "reim", "reimann", "reimer", "reimers", "rein",
    "reinartz", "reindl", "reinecke", "reineke", "reiner", "reiners", "reinert", "reinhardt",
    "reinhart", "reinhold", "reinke", "reinsch", "reis", "reisch", "reischl", "reiser",
    "reiss", "reiß", "reiter", "reith", "reitz", "remmert", "rempel", "remy", "rendl",
    "renger", "renk", "renner", "rensing", "rentsch", "renz", "resch", "reschke", "rettig",
    "retzlaff", "reusch", "reuss", "reuß", "reuter", "reuther", "röder", "rhein", "ribbeck",
    "richartz", "richter", "ridder", "riebel", "rieck", "ried", "riedel", "rieder", "riedl",
    "riegel", "rieger", "riehl", "riehm", "riemer", "ries", "riese", "riess", "rieß",
    "rieth", "rill", "ring", "ringel", "rink", "rinke", "rippl", "risch", "risse", "rist",
    "ritt", "ritter", "ode", "ritschel", "ritz", "rix", "robben", "roberts", "roch",
    "rock", "rode", "roder", "roediger", "roehl", "roehm", "roehr", "roehrig", "roemer",
    "roesch", "roesler", "roesner", "roessler", "roettger", "roggenbuck", "rohde", "rohe",
    "rohleder", "rohlfs", "rohm", "rohr", "rohrbach", "rohrer", "roll", "roller", "roloff",
    "rommel", "roos", "rosch", "rose", "rosen", "rosenbaum", "rosenberg", "rosenberger",
    "rosendahl", "rosenkranz", "rosenthal", "rosin", "rosner", "ross", "rossi", "rossmann",
    "rost", "roß", "roßmann", "roth", "rothe", "rothenberg", "rother", "rothmann", "rott",
    "rotter", "rottmann", "uck", "rudloff", "rudolph", "ruecker", "rueckert", "ruoff",
    "ruediger", "ruehl", "ruehle", "ruemenapf", "ruempker", "rueth", "ruf", "ruff", "ruge",
    "ruhl", "ruhland", "rump", "rumpf", "runge", "funk", "ruoff", "rupp", "ruppel",
    "ruppert", "rupprecht", "rusch", "rust", "ruth", "rutkowski", "utz", "röder", "röhl",
    "röhm", "röhr", "röhrig", "römer", "rösch", "rösler", "rösner", "rößler", "röttger",
    "rücker", "rückert", "rühl", "rühle", "saal", "saathoff", "sacher", "sachs", "sachse",
    "sack", "sadowski", "saenger", "sager", "sahm", "sailer", "salomon", "salzmann",
    "sammer", "sand", "sander", "sanders", "sandmann", "sandner", "sanger", "sasse",
    "sattler", "sauer", "sauermann", "saul", "sauter", "sautter", "schaaf", "schaal",
    "schaar", "schab", "schach", "schacht", "schack", "schad", "schade", "schaefer",
    "schaefers", "schaeffer", "schaeffler", "schaer", "schaetzle", "schaffer", "schalk",
    "schall", "schaller", "schanz", "schaper", "scharf", "scharfe", "scharrer", "schatz",
    "schaub", "schauer", "scheck", "schedel", "scheel", "scheele", "scheer", "scheerer",
    "scheffel", "scheffler", "scheibe", "scheibler", "scheid", "scheidt", "schell",
    "schelle", "schellenberg", "scheller", "schenk", "schenke", "schenkel", "schepers",
    "scherer", "scherf", "scherzer", "scheu", "scheuer", "scheuermann", "scheurer",
    "schick", "schiebel", "schiefer", "schiel", "schiele", "schiemann", "schier",
    "schifer", "schiffbauer", "schiffer", "schiffmann", "schild", "schill", "schiller",
    "schilling", "schimanski", "schimmel", "schimpf", "schindler", "schink", "schinke",
    "schinner", "schipper", "schirmer", "schirra", "schlaegel", "schlaeger", "schlecht",
    "schlegel", "schleich", "schleicher", "schleifer", "schlemmer", "schlenker",
    "schlesinger", "schlicht", "schlichting", "schlick", "schlosser", "schluter",
    "schlueter", "schlüter", "schmal", "schmalz", "schmelz", "schmelzer", "schmid",
    "schmidbauer", "schmidl", "schmidt", "schmidtke", "schmied", "schmieder", "schmiedl",
    "schmitt", "schmitz", "schmoll", "schmuck", "schnabel", "ur", "schneck", "schneider",
    "schnell", "schnelle", "schneller", "schnitzer", "schnitzler", "schnoor", "schnurr",
    "schober", "schoch", "schock", "schoeler", "schoen", "schoenauer", "schoenberg",
    "schoenberger", "schoene", "schoenemann", "schoener", "schoenfeld", "schoenfelder",
    "schoenherr", "schoening", "schoepf", "schoepp", "scholl", "scholz", "scholze",
    "schomaker", "schon", "schopf", "schorn", "schorr", "schott", "schrader", "schrage",
    "schramm", "schrammel", "schranz", "schreck", "schreiber", "schreiner", "schreiter",
    "schrempp", "schreyer", "schroeder", "schroer", "schroeter", "schroll", "schroth",
    "schröder", "schröer", "schröter", "schubert", "schuch", "schuchardt", "schuck",
    "schuehle", "schueler", "schueller", "schuemann", "schuenemann", "schuerer",
    "schuermann", "schuette", "schuetz", "schuetze", "schuh", "schuhmacher", "schuhmann",
    "schuldt", "schule", "schuler", "schuller", "schult", "schulte", "schulten", "schultes",
    "schultheis", "schultheiss", "schultheiß", "schultz", "schulz", "schulze", "schumacher",
    "schumann", "schunk", "schupp", "schur", "schurig", "schuster", "schwaab", "schwab",
    "schwabe", "schwaiger", "schwalb", "schwalbe", "schwan", "schwandt", "schwanke",
    "schwartz", "schwarz", "schwarze", "schwarzer", "schwarzkopf", "schwebel", "schweiger",
    "schweigert", "schweitzer", "schweizer", "schwenk", "schwenke", "schwerdtfeger",
    "schwerin", "schwerte", "schwind", "schwing", "schwinn", "schäfer", "schäfers",
    "schäffer", "schäffler", "schätzle", "schöler", "schön", "schönauer", "schönberg",
    "schönberger", "schöne", "schönemann", "schöner", "schönfeld", "schönfelder",
    "schönherr", "schöning", "schöpf", "schüler", "schüller", "schümann", "schünemann",
    "schürer", "schürmann", "schütte", "schütz", "schütze", "sebald", "sebesta", "seck",
    "sedlmeier", "seeger", "seel", "seeler", "seelig", "seeliger", "seemann", "seger",
    "seib", "seibel", "seibert", "seidel", "seidensticker", "seidl", "seidler", "seifert",
    "seiffert", "seiler", "seitz", "selig", "sell", "selle", "semmler", "sendler", "senf",
    "senft", "senger", "senn", "serfling", "severin", "seydel", "seyfarth", "seyler",
    "sieben", "sieber", "siebert", "siebrecht", "siedler", "siegel", "sieger", "siegert",
    "siegl", "siegmund", "sieker", "sielaff", "siemens", "siemers", "sieveking", "sievers",
    "sievert", "siewert", "sigl", "sikora", "silber", "simm", "simmer", "sinemus", "singer",
    "sinn", "sippel", "skowronek", "slaby", "smidt", "sobotka", "soellner", "soerensen",
    "soika", "soldan", "solf", "soll", "sommer", "sommerfeld", "sondermann", "sonnenberg",
    "sonntag", "sorge", "sorg", "spach", "spaeth", "spahn", "spalt", "spangenberg",
    "spanier", "specht", "speck", "speer", "speidel", "spengler", "sperber", "sperl",
    "sperling", "spiegel", "spiekermann", "spielmann", "spies", "spiess", "spieß",
    "spindler", "spitz", "spitzer", "spoerl", "spohn", "sporer", "sprecher", "spreitzer",
    "sprenger", "springer", "späth", "spörl", "staab", "staat", "stach", "stadelmann",
    "stadler", "stadtler", "staebler", "staehler", "stahl", "stahlschmidt", "staiger",
    "stallmann", "stamm", "stammel", "stammer", "stampf", "stang", "stange", "angl",
    "stangl", "stapf", "stark", "starke", "staub", "stauch", "staudacher", "staude",
    "staudinger", "staudt", "stauffer", "stebler", "stecher", "steck", "steckel",
    "steffens", "stegemann", "steger", "stegmaier", "stegmann", "stegmüller", "ib", "stehle",
    "stehling", "steidle", "steig", "steiger", "steigerwald", "stein", "steinbach",
    "steinbauer", "steinberg", "steinberger", "steinborn", "steinbrecher", "steinbrück",
    "steiner", "steinert", "steinhauer", "steinhaus", "steinhauser", "steinhoff",
    "steininger", "steinkamp", "steinke", "steinle", "steinmann", "steinmetz", "steinmüller",
    "steins", "stella", "stelljes", "stellmacher", "stelter", "stelzer", "stelzner",
    "stemmer", "stemmler", "stender", "stengel", "stenger", "stenzel", "stephan", "stern",
    "sternberg", "stetter", "steuernagel", "stich", "stickel", "stief", "stiefel", "stiegler",
    "stiehl", "stier", "stiller", "stock", "stocker", "stockmann", "stoeber", "stoecker",
    "stoeckl", "stoehr", "stoermer", "stoessel", "stoll", "stolle", "stolz", "stolze",
    "stopp", "storch", "storck", "stork", "storm", "storz", "stoss", "stoß", "strack",
    "stracke", "strahl", "strasser", "straub", "straube", "strauch", "strauss", "strauß",
    "strebel", "strecker", "strehl", "strehle", "streib", "streicher", "streit", "streller",
    "streng", "streubel", "stricker", "striebel", "strobel", "strobl", "stroh", "strohm",
    "strohmaier", "strohmeier", "strohmeyer", "strube", "struck", "strunz", "struve",
    "sträter", "ströbel", "stubbe", "stuber", "stuck", "ucke", "stucky", "studer", "stueber",
    "stueck", "stuhlmann", "stumm", "stumpf", "sturm", "stutz", "stöber", "stöcker",
    "stöckl", "stöhr", "störmer", "stößel", "stüber", "suess", "suhr", "sulzer", "sutter",
    "swoboda", "sydow", "szabo", "szymanski", "sänger", "söllner", "sörensen", "süß",
    "tafel", "tamm", "tanner", "tappert", "taschner", "taube", "tauber", "taubert",
    "tauchnitz", "tauscher", "tegtmeier", "teichert", "teichmann", "teller", "tempel",
    "tenbieg", "tepe", "terpitz", "tesch", "teschner", "teske", "tetzlaff", "teuber",
    "teubner", "teufel", "tewes", "thaler", "thalhammer", "thamm", "theil", "theilen",
    "theis", "theisen", "theiss", "theißen", "thelen", "theobald", "thiel", "thiele",
    "thielemann", "thielen", "thiemann", "thieme", "thier", "thies", "thiessen", "thimm",
    "thoene", "thoma", "thomae", "thomann", "thoms", "thomsen", "thorenz", "thorwart",
    "thum", "thumm", "thöne", "tiedemann", "tietjen", "tietz", "tietze", "tillmann",
    "timm", "timmermann", "timpe", "tischer", "tischler", "tittel", "tobben", "toepfer",
    "toelle", "tonn", "topp", "tost", "trapp", "traub", "traenkler", "traut", "trautmann",
    "trautwein", "treiber", "tremmel", "trenkler", "tretter", "treu", "triebel", "triller",
    "trinks", "tritschler", "troeger", "troester", "troll", "trommer", "trost", "tröger",
    "tröster", "tschirner", "tucholski", "türk", "tölle", "töpfer", "uebel", "uecker",
    "uhde", "uhl", "uhlemann", "uhlig", "uhlmann", "ulbricht", "ullmann", "ullrich", "ulm",
    "ulmer", "umbach", "unbekannt", "unger", "ungerer", "unruh", "unterberger", "urban",
    "urbanek", "usadel", "utz", "vahrenkamp", "vatter", "veh", "veith", "velten", "venzke",
    "vetter", "viehmann", "vieregge", "vierling", "vieth", "vietor", "vilser", "voelker",
    "voelkl", "vogel", "vogelsang", "vogler", "vogt", "voigt", "voigtländer", "voit",
    "volk", "volkert", "volkmann", "voll", "vollmann", "vollmer", "vollrath", "volz",
    "vormann", "voss", "voß", "völk", "völker", "völkl", "waack", "wache", "wachter",
    "wachtel", "wacker", "wagener", "wagenknecht", "wagner", "wahl", "wahle", "waibel",
    "walch", "wald", "waldeck", "walder", "waldmann", "waldner", "walker", "wall", "wallner",
    "walsch", "walser", "walther", "walz", "wamser", "wand", "wanke", "wanner", "warnke",
    "waschk", "wasser", "wassermann", "weber", "wechsler", "weck", "wecker", "wedekind",
    "wedel", "wegener", "weber", "weger", "weghorst", "wegmann", "wegner", "wehner", "wehr",
    "wehrle", "wehrmann", "weber", "weibel", "weichelt", "weichert", "weick", "weid",
    "weide", "weidemann", "weiden", "weidlich", "weidmann", "weidner", "weigand", "weigel",
    "weigelt", "weigl", "weihe", "weiher", "weil", "weiland", "weiler", "weimann", "weimer",
    "wein", "weinberg", "weinberger", "weiner", "weinert", "weingärtner", "weingarten",
    "weingartner", "weinhold", "weinmann", "weinreich", "weins", "weis", "weise", "weiser",
    "weishaupt", "weiss", "weisse", "weisser", "weissmann", "weit", "weitz", "weitzel",
    "weiß", "weiße", "weißer", "weißmann", "welcker", "welk", "welker", "weller", "wellmann",
    "welsch", "welte", "welter", "welz", "welzel", "wendel", "wendenburg", "wenderoth",
    "wendland", "wendler", "wendt", "wenger", "wenig", "wenk", "wenke", "wenzel", "werle",
    "wermuth", "wernecke", "wernicke", "werth", "wertz", "wesch", "wesemann", "wessel",
    "wessels", "wessely", "west", "wetzel", "wester", "westermann", "westphal", "wetzel",
    "weyer", "weyers", "wichmann", "wick", "wicke", "widmann", "widmer", "wiebe", "wiechert",
    "wiechmann", "wieczorek", "wiedemann", "wiedenmann", "wieder", "wiedmann", "wiegand",
    "wiegel", "wieger", "wiegmann", "wiehe", "wieland", "wiemann", "wiemer", "wiener",
    "wieneke", "wiens", "wierer", "wiese", "wieser", "wiesmann", "wiesner", "wiest",
    "wilczek", "wild", "wilde", "wildner", "wilke", "wilken", "wilkens", "will", "wille",
    "willers", "willmann", "willms", "wilms", "wimmer", "wind", "windisch", "windhorst",
    "wingert", "winkel", "winkelmann", "winkler", "winter", "winzer", "wippermann", "wirth",
    "wirths", "wirtz", "wischnewski", "wisniewski", "wissel", "witt", "witte", "wittek",
    "wittenberg", "wittich", "wittig", "wittke", "wittmann", "wittwer", "witzel", "witzke",
    "wlodarczyk", "woehl", "woehrmann", "woelki", "woerner", "wohlfahrt", "wohlfart",
    "wohlfeil", "wohlgemuth", "wojcik", "wolf", "wolff", "wolfram", "wolfrum", "woll",
    "wollmann", "wollny", "wollschläger", "wolter", "wolters", "wondra", "worm", "worschech",
    "wozniak", "wrede", "wright", "wrobel", "wucherpfennig", "wuensche", "wuerfel", "wuest",
    "wulf", "wulff", "wunder", "wunderlich", "wurm", "wurst", "wurster", "wuttke", "wähler",
    "wöhl", "wöhrmann", "wölki", "wörner", "wünsche", "würfel", "wüst", "zabel", "zach",
    "zacharias", "zacher", "zahn", "zajac", "zander", "zanker", "zapf", "zaremba", "zauner",
    "zech", "zedler", "zeh", "zehender", "zehn", "zehnder", "zeidler", "zeiler", "zeiner",
    "zeis", "zeitler", "zelinka", "zeller", "zellner", "zemke", "zenger", "zenk", "zenker",
    "zepf", "zerbe", "zettel", "zetzsche", "zeuner", "zeyer", "ziebarth", "ziegler", "zielke",
    "ziemann", "ziemer", "ziemssen", "zier", "zierer", "zietlow", "zill", "ziller", "zillmann",
    "zimmer", "zimmerer", "zimmermann", "zink", "zinke", "zinn", "zinsmeister", "zipfel",
    "zipperer", "zirpel", "zitzmann", "zobel", "zoellner", "zoll", "zoller", "zollner",
    "zorn", "zuber", "zucker", "zuehlke", "zuelch", "zuendel", "zumbusch", "zwick",
    "zwicker", "zöllner", "zühlke", "zülch", "zündel",
})

SURNAME_SUFFIXES = (
    "mann", "müller", "mueller", "meier", "meyer", "maier", "mayr", "mayer",
    "schulz", "schulze", "schmidt", "schmitt", "schmitz", "schneider", "fischer",
    "weber", "wagner", "becker", "bauer", "richter", "schröder", "schroeder",
    "zimmer", "krüger", "krueger", "meister", "hofer", "huber", "berger",
    "winkler", "bacher", "steiner", "felder", "macher", "gruber", "reuter",
    "häuser", "haeuser", "dörfer", "doerfer", "stetter", "knecht", "schläger",
    "schlaeger", "händler", "haendler", "bäcker", "baecker", "köhler", "koehler",
    "jäger", "jaeger", "gärtner", "gaertner", "förster", "foerster", "müller",
    "ović", "ovic", "ević", "evic", "owski", "ewski", "inski", "iński", "czyk",
    "czak", "enko", "chuk", "oğlu", "oglu",
)


def compact_name(value):
    return re.sub(r"[\s,]+", "", unicodedata.normalize("NFC", value).casefold())


def _clean_token(token: str) -> str:
    return unicodedata.normalize("NFC", token or "").strip(" \t\r\n.,;:()[]{}\"'").casefold()


def has_surname_prefix(part: str) -> bool:
    norm = unicodedata.normalize("NFC", part or "").strip().casefold()
    if any(norm.startswith(prefix) for prefix in MULTIWORD_SURNAME_PREFIXES):
        return True
    words = norm.split()
    if len(words) >= 2 and words[0] in SURNAME_PARTICLES:
        return True
    if norm.startswith(("mc", "mac", "o'", "o’")) and len(norm) >= 4 and norm not in KNOWN_GIVEN_NAMES:
        return True
    return False


def classify_name_token(part: str) -> str:
    """Classify a single name part into 'given', 'family', or 'unknown'."""
    if not part or not any(c.isalpha() for c in part):
        return "unknown"
    if has_surname_prefix(part):
        return "family"
    words = [w for w in re.split(r"\s+", part.strip()) if w]
    if len(words) > 1:
        cleaned_words = [_clean_token(w) for w in words]
        if any(w in SURNAME_PARTICLES for w in cleaned_words[:-1]):
            return "family"
        if all(w in KNOWN_GIVEN_NAMES for w in cleaned_words if w):
            return "given"
        if any(w in PURE_SURNAMES and w not in KNOWN_GIVEN_NAMES for w in cleaned_words):
            return "family"
        return "unknown"
    token = _clean_token(words[0])
    if not token:
        return "unknown"
    if "-" in token:
        subtokens = [sub for sub in token.split("-") if sub]
        if len(subtokens) >= 2:
            if all(sub in KNOWN_GIVEN_NAMES for sub in subtokens):
                return "given"
            if any(sub in PURE_SURNAMES and sub not in KNOWN_GIVEN_NAMES for sub in subtokens):
                return "family"
            if any(len(sub) >= 5 and sub.endswith(SURNAME_SUFFIXES) and sub not in KNOWN_GIVEN_NAMES for sub in subtokens):
                return "family"
    is_given = token in KNOWN_GIVEN_NAMES
    is_pure_surname = (
        token in PURE_SURNAMES
        or (len(token) >= 5 and token.endswith(SURNAME_SUFFIXES))
    ) and not is_given
    if is_given and not is_pure_surname:
        return "given"
    if is_pure_surname:
        return "family"
    return "unknown"


def classify_name_pair(left: str, right: str) -> tuple[str, str, str, str] | None:
    """Return (order, first_name, last_name, rule) when row-individual evidence is unambiguous."""
    if not left or not right:
        return None
    if not all(any(c.isalpha() for c in part) and not any(c.isdigit() for c in part) for part in (left, right)):
        return None
    left_kind = classify_name_token(left)
    right_kind = classify_name_token(right)
    if left_kind == "given" and right_kind in ("family", "unknown"):
        return "given_family", left.strip(), right.strip(), "lexical_given_family"
    if right_kind == "given" and left_kind in ("family", "unknown"):
        return "family_given", right.strip(), left.strip(), "lexical_family_given"
    if left_kind == "family" and right_kind == "unknown":
        return "family_given", right.strip(), left.strip(), "lexical_family_given"
    if right_kind == "family" and left_kind == "unknown":
        return "given_family", left.strip(), right.strip(), "lexical_given_family"
    return None


def infer_column_tiebreaker(values, default_order: str = DEFAULT_ORDER) -> str:
    """Compute column-wide majority orientation strictly from unambiguous rows as tie-breaker."""
    counts = {"given_family": 0, "family_given": 0}
    for item in values or ():
        if isinstance(item, (tuple, list)) and len(item) == 2:
            left, right = str(item[0] or "").strip(), str(item[1] or "").strip()
            classified = classify_name_pair(left, right)
            if classified is not None:
                counts[classified[0]] += 1
            continue
        text = str(item or "").strip()
        if not text or any(c.isdigit() for c in text):
            continue
        if text.count(",") == 1:
            last, first = (part.strip() for part in text.split(",", 1))
            if all(part and any(c.isalpha() for c in part) for part in (first, last)):
                counts["family_given"] += 1
        elif "," not in text and len(text.split()) == 2:
            left, right = text.split()
            classified = classify_name_pair(left, right)
            if classified is not None:
                counts[classified[0]] += 1
    if counts["given_family"] > counts["family_given"]:
        return "given_family"
    if counts["family_given"] > counts["given_family"]:
        return "family_given"
    return default_order if default_order in ("given_family", "family_given") else DEFAULT_ORDER


def split_combined_name(value, default_order=DEFAULT_ORDER):
    """A comma separates whole parts; 2-part names prioritize row-level lexical evidence over default_order."""
    if not value or any(c.isdigit() for c in value):
        return None
    if value.count(",") == 1:
        last, first = (part.strip() for part in value.split(",", 1))
        rule = "explicit_surname_comma_given_name"
    elif "," not in value and len(value.split()) == 2 and default_order != "unknown":
        left, right = value.split()
        classified = classify_name_pair(left, right)
        if classified is not None:
            _, first, last, rule = classified
        else:
            first, last = (right, left) if default_order == "family_given" else (left, right)
            rule = "default_name_group_order"
    else:
        return None
    if not all(part and any(c.isalpha() for c in part) for part in (first, last)):
        return None
    return first, last, rule


def matching_name_cells(cells, first, last):
    """Use only the cell completely covered by the model's observed name parts."""
    if not first or not last:
        return []
    parts = [compact_name(first), compact_name(last)]
    return [cell for cell in cells if cell.get("text")
            and compact_name(cell["text"]) in ("".join(parts), "".join(reversed(parts)))]


def matching_comma_cells(cells, first, last):
    return [cell for cell in matching_name_cells(cells, first, last)
            if "," in cell.get("text", "") and split_combined_name(cell["text"], "unknown")]
