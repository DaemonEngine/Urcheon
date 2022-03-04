# This file allows building and running the software with the Nix package
# manager, used in NixOS or on another distribution.

{
  description = "a toolset to manage and build `pk3` or `dpk` source directories";

  inputs = {
    nixpkgs.url = "flake:nixpkgs";

    crunch.url = "github:DaemonEngine/crunch";
    crunch.inputs.nixpkgs.follows = "nixpkgs";

    netradiant.url = "gitlab:xonotic/netradiant";
    netradiant.inputs.nixpkgs.follows = "nixpkgs";

    sloth.url = "github:Unvanquished/Sloth";
    sloth.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, crunch, netradiant, sloth }:
    let
      pkgs = nixpkgs.legacyPackages.x86_64-linux;
    in {

      packages.x86_64-linux = {
        iqmtool =
          pkgs.stdenv.mkDerivation {
            name = "iqmtool";
            src = pkgs.fetchsvn {
              # this is an old-ish, better tested version
              url = "http://svn.code.sf.net/p/fteqw/code/trunk/iqm/";
              rev = 5570;
              sha256 = "sha256-o6ZufY8dNjf1Bl14knkrgpo/JyPnP8uU516CFVzvZAk=";
            };

            buildInputs = with pkgs; [
              gcc gnumake
            ];

            installPhase = ''
              if [ -f iqmtool ]; then
                install -Dm0755 iqmtool -T $out/bin/iqmtool
              else
                install -Dm0755 iqm -T $out/bin/iqmtool
              fi
            '';
          };

        urcheon = pkgs.python310.pkgs.buildPythonPackage {
          name = "urcheon";

          src = pkgs.lib.cleanSource ./.;

          format = "other";

          buildInputs = [
            (pkgs.python310.withPackages
              (ps: [ ps.colorama ps.psutil ps.toml ps.pillow ]))
          ];

          propagatedBuildInputs = with pkgs; [
            netradiant.packages.x86_64-linux.quake-tools
            crunch.defaultPackage.x86_64-linux
            sloth.defaultPackage.x86_64-linux
            opusTools
            libwebp
          ];

          installPhase = ''
            runHook preInstall

            mkdir $out/
            cp -ra bin/ profile/ Urcheon/ $out/

            runHook postInstall
          '';
        };

        crunch = crunch.defaultPackage.x86_64-linux;
        sloth = sloth.defaultPackage.x86_64-linux;
      } // netradiant.packages.x86_64-linux;

      apps.x86_64-linux = {
        iqmtool = {
          type = "app";
          program = "${self.packages.x86_64-linux.iqmtool}/bin/iqmtool";
        };

        urcheon = {
          type = "app";
          program = "${self.packages.x86_64-linux.urcheon}/bin/urcheon";
        };

        esquirel = {
          type = "app";
          program = "${self.packages.x86_64-linux.urcheon}/bin/esquirel";
        };

        crunch = crunch.defaultApp.x86_64-linux;
        sloth = sloth.defaultApp.x86_64-linux;
      };

    };
}
